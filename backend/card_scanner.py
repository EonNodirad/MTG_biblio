"""
Perceptual-hash card scanner loaded once at startup.

Flow:
  1. detect_card()  — OpenCV finds the card rectangle in the frame
  2. perspective_correct() — warps the quad to a flat 488×680 image
  3. phash on art crop of the corrected card
  4. nearest-neighbour search in the index
"""

import io
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import imagehash
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

INDEX_DB = Path(__file__).parent.parent / "ml" / "index.db"

# Thresholds (out of 64 bits)
THRESHOLD_HIGH   = 8
THRESHOLD_MEDIUM = 13
THRESHOLD_LOW    = 18   # au-delà → "none", évite les faux positifs

# Standard card output size after perspective correction
CARD_W, CARD_H = 488, 680


# ---------------------------------------------------------------------------
# Card detection helpers
# ---------------------------------------------------------------------------

def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 points: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # top-left
    rect[2] = pts[np.argmax(s)]   # bottom-right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left
    return rect


def detect_card(img_bgr: np.ndarray) -> np.ndarray | None:
    """
    Detect a card-shaped rectangle in the frame.
    Filters on: aspect ratio, solidity, and size range.
    Returns ordered 4 points [[x,y], ...] or None if not found.
    """
    fh, fw = img_bgr.shape[:2]
    frame_area = fw * fh
    min_area = frame_area * 0.04   # carte = au moins 4% de la frame
    max_area = frame_area * 0.80   # pas toute la frame (mains etc)

    gray  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blur  = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 30, 100)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges  = cv2.dilate(edges, kernel, iterations=2)
    edges  = cv2.erode(edges, kernel, iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_box   = None
    best_score = 0.0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if not (min_area <= area <= max_area):
            continue

        # Enveloppe convexe — donne un contour propre même avec des doigts qui dépassent
        hull      = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        if hull_area == 0:
            continue

        # Solidité : le contour doit être presque convexe (carte ≥ 0.80)
        solidity = area / hull_area
        if solidity < 0.78:
            continue

        # Ratio largeur/hauteur via minAreaRect sur le hull
        rect     = cv2.minAreaRect(hull)
        rw, rh   = rect[1]
        if rw == 0 or rh == 0:
            continue
        ratio = min(rw, rh) / max(rw, rh)

        # Carte MTG : 63×88mm = 0.716 — on accepte 0.60–0.82
        if not (0.60 <= ratio <= 0.82):
            continue

        # Score : favorise grande taille + solidité + ratio proche de 0.716
        score = area * solidity * (1 - abs(ratio - 0.716) * 4)
        if score > best_score:
            best_score = score
            best_box   = cv2.boxPoints(rect).astype(np.float32)

    if best_box is None:
        return None
    return _order_points(best_box)


def perspective_correct(img_bgr: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """Warp the detected quad to a standard CARD_W × CARD_H rectangle."""
    dst = np.array([
        [0,        0       ],
        [CARD_W-1, 0       ],
        [CARD_W-1, CARD_H-1],
        [0,        CARD_H-1],
    ], dtype=np.float32)
    M = cv2.getPerspectiveTransform(quad, dst)
    return cv2.warpPerspective(img_bgr, M, (CARD_W, CARD_H))


def _guide_box(fh: int, fw: int) -> tuple[int, int, int, int]:
    """Centre crop aux proportions carte MTG (ratio 0.716), 60% de la hauteur."""
    card_h = int(fh * 0.60)
    card_w = int(card_h * 0.716)
    cx, cy = fw // 2, fh // 2
    x1 = cx - card_w // 2
    y1 = cy - card_h // 2
    return x1, y1, x1 + card_w, y1 + card_h


def _art_crop(pil_img: Image.Image) -> Image.Image:
    """Crop to the illustration area (avoids frame bias)."""
    w, h = pil_img.size
    return pil_img.crop((
        int(w * 0.06),
        int(h * 0.08),
        int(w * 0.94),
        int(h * 0.48),
    ))


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

@dataclass
class ScanResult:
    uuid: str
    scryfall_id: str
    distance: int
    confidence: str                      # "high" | "medium" | "low" | "none"
    quad: list[list[float]] = field(default_factory=list)   # contour détecté (optionnel)
    guide: list[float] = field(default_factory=list)        # [x1,y1,x2,y2] normalisé 0-1


class CardScanner:
    def __init__(self, index_path: Path = INDEX_DB):
        self._uuids: list[str] = []
        self._scryfall_ids: list[str] = []
        self._hashes: np.ndarray
        self._load(index_path)

    def _load(self, path: Path) -> None:
        logger.info("Loading card hash index from %s…", path)
        conn = sqlite3.connect(path)
        rows = conn.execute("SELECT uuid, scryfall_id, phash FROM card_hashes").fetchall()
        conn.close()
        self._uuids        = [r[0] for r in rows]
        self._scryfall_ids = [r[1] for r in rows]
        self._hashes = np.array(
            [imagehash.hex_to_hash(r[2]).hash.flatten() for r in rows],
            dtype=bool,
        )
        logger.info("Scanner index: %d cards", len(self._uuids))

    def _phash_match(self, pil_img: Image.Image) -> tuple[int, int]:
        """Return (index, distance) of the nearest card in the index."""
        art = _art_crop(pil_img)
        h   = imagehash.phash(art, hash_size=8)
        q   = h.hash.flatten()
        distances = np.sum(self._hashes ^ q, axis=1)
        idx = int(np.argmin(distances))
        return idx, int(distances[idx])

    def find(self, image_bytes: bytes) -> ScanResult | None:
        """
        Detect card in frame, correct perspective, then identify via pHash.
        Returns ScanResult with quad coordinates (relative 0-1) for frontend overlay.
        """
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            logger.warning("Cannot decode image")
            return None

        fh, fw = img_bgr.shape[:2]

        # Guide crop — direct, sans detect_card (plus rapide et plus fiable)
        x1, y1, x2, y2 = _guide_box(fh, fw)
        crop    = img_bgr[y1:y2, x1:x2]
        pil_img = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        quad_rel = []

        idx, dist = self._phash_match(pil_img)

        if dist <= THRESHOLD_HIGH:
            conf = "high"
        elif dist <= THRESHOLD_MEDIUM:
            conf = "medium"
        elif dist <= THRESHOLD_LOW:
            conf = "low"
        else:
            conf = "none"

        guide_rel = [x1/fw, y1/fh, x2/fw, y2/fh]

        return ScanResult(
            uuid=self._uuids[idx],
            scryfall_id=self._scryfall_ids[idx],
            distance=dist,
            confidence=conf,
            quad=quad_rel,
            guide=guide_rel,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_scanner: CardScanner | None = None


def load_scanner() -> None:
    global _scanner
    if not INDEX_DB.exists():
        logger.warning("Scanner index not found at %s — /api/scan unavailable", INDEX_DB)
        return
    _scanner = CardScanner()


def get_scanner() -> CardScanner | None:
    return _scanner


def rebuild_index_incremental() -> dict:
    """Run build_index.py to add hashes for cards not yet in the index."""
    import subprocess
    import sys
    from mtgjson.loader import DB_FILE as MTGJSON_DB
    build_script = INDEX_DB.parent / "build_index.py"
    if not build_script.exists():
        logger.warning("build_index.py not found at %s — skipping", build_script)
        return {"success": False, "reason": "build_script_not_found"}
    logger.info("Starting incremental index rebuild…")
    result = subprocess.run(
        [sys.executable, str(build_script), "--workers", "4", "--db", str(MTGJSON_DB)],
        cwd=str(INDEX_DB.parent),
        capture_output=True,
        text=True,
        timeout=7200,
    )
    if result.returncode == 0:
        load_scanner()
        return {"success": True}
    logger.error("build_index.py failed: %s", result.stderr[-500:])
    return {"success": False, "reason": result.stderr[-200:]}
