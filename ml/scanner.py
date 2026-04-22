"""
Card scanner — perceptual hash nearest-neighbour search.

As a module:
    from scanner import CardScanner
    scanner = CardScanner()          # loads index into RAM once
    result  = scanner.find(img_bytes)
    # result = {"uuid": "...", "scryfall_id": "...", "distance": 3, "confidence": "high"}

As a CLI (webcam test):
    python scanner.py
"""

import io
import logging
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import imagehash
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

INDEX_DB = Path(__file__).parent / "index.db"

# Distance thresholds (out of 64 bits)
THRESHOLD_HIGH   = 8   # very confident
THRESHOLD_MEDIUM = 15  # probably right
THRESHOLD_LOW    = 22  # uncertain


@dataclass
class ScanResult:
    uuid: str
    scryfall_id: str
    distance: int
    confidence: str  # "high" | "medium" | "low" | "none"


class CardScanner:
    def __init__(self, index_path: Path = INDEX_DB):
        if not index_path.exists():
            raise FileNotFoundError(f"Index not found: {index_path}. Run build_index.py first.")
        self._uuids: list[str] = []
        self._scryfall_ids: list[str] = []
        self._hashes: np.ndarray  # shape (N,), dtype=uint64
        self._load(index_path)

    def _load(self, path: Path) -> None:
        logger.info("Loading card hash index from %s…", path)
        conn = sqlite3.connect(path)
        rows = conn.execute("SELECT uuid, scryfall_id, phash FROM card_hashes").fetchall()
        conn.close()

        self._uuids       = [r[0] for r in rows]
        self._scryfall_ids = [r[1] for r in rows]
        # Convert hex strings to uint64 numpy array for fast XOR
        self._hashes = np.array([int(r[2], 16) for r in rows], dtype=np.uint64)
        logger.info("Index loaded: %d cards", len(self._uuids))

    def _hamming_distances(self, query_int: int) -> np.ndarray:
        """Vectorised Hamming distances via XOR + popcount lookup."""
        xored = self._hashes ^ np.uint64(query_int)
        # Popcount via 16-bit lookup table (fast)
        lut = np.array([bin(i).count("1") for i in range(65536)], dtype=np.uint8)
        d = (
            lut[xored        & np.uint64(0xFFFF)] +
            lut[(xored >> 16) & np.uint64(0xFFFF)] +
            lut[(xored >> 32) & np.uint64(0xFFFF)] +
            lut[(xored >> 48) & np.uint64(0xFFFF)]
        )
        return d

    def find(self, image_bytes: bytes) -> ScanResult | None:
        """Find the closest card for an image given as raw bytes."""
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as e:
            logger.warning("Cannot decode image: %s", e)
            return None

        h = imagehash.phash(img)
        query_int = int(str(h), 16)

        distances = self._hamming_distances(query_int)
        idx = int(np.argmin(distances))
        dist = int(distances[idx])

        if dist <= THRESHOLD_HIGH:
            confidence = "high"
        elif dist <= THRESHOLD_MEDIUM:
            confidence = "medium"
        elif dist <= THRESHOLD_LOW:
            confidence = "low"
        else:
            confidence = "none"

        return ScanResult(
            uuid=self._uuids[idx],
            scryfall_id=self._scryfall_ids[idx],
            distance=dist,
            confidence=confidence,
        )


# ---------------------------------------------------------------------------
# CLI — webcam test
# ---------------------------------------------------------------------------

def _cli_test() -> None:
    import time
    try:
        import cv2
    except ImportError:
        print("Install opencv-python to use the webcam CLI: pip install opencv-python")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    scanner = CardScanner()

    # Load card names from MTGjson for display
    mtgjson_db = Path(__file__).parent.parent / "backend" / "data" / "AllPrintings.sqlite"
    name_cache: dict[str, str] = {}
    if mtgjson_db.exists():
        conn = sqlite3.connect(mtgjson_db)
        for row in conn.execute("SELECT uuid, name FROM cards"):
            name_cache[row[0]] = row[1]
        conn.close()

    import urllib.request

    CONF_COLOR = {
        "high":   (0, 220, 0),    # vert
        "medium": (0, 180, 255),  # orange
        "low":    (0, 80, 255),   # rouge
        "none":   (80, 80, 80),   # gris
    }
    BORDER = 6  # épaisseur du cadre de confiance

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open webcam.")
        sys.exit(1)

    print("Press Q to quit. Hold a card in front of the camera.")

    last_scan   = 0.0
    SCAN_INTERVAL = 0.5  # secondes entre chaque scan

    current_result: ScanResult | None = None
    card_thumb: "np.ndarray | None" = None  # miniature BGR de la carte trouvée

    def fetch_thumb(scryfall_id: str) -> "np.ndarray | None":
        url = f"https://cards.scryfall.io/small/front/{scryfall_id[0]}/{scryfall_id[1]}/{scryfall_id}.jpg"
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                data = r.read()
            arr = np.frombuffer(data, np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception:
            return None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w = frame.shape[:2]
        now = time.time()

        if now - last_scan >= SCAN_INTERVAL:
            last_scan = now
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            result = scanner.find(buf.tobytes())
            # Ne met à jour la miniature que si la carte change
            if result and result.confidence != "none":
                if current_result is None or current_result.uuid != result.uuid:
                    card_thumb = fetch_thumb(result.scryfall_id)
                current_result = result
            else:
                current_result = None
                card_thumb = None

        # --- Cadre coloré selon confiance ---
        conf = current_result.confidence if current_result else "none"
        color = CONF_COLOR[conf]
        cv2.rectangle(frame, (0, 0), (w - 1, h - 1), color, BORDER)

        # --- Miniature carte en bas à droite ---
        if card_thumb is not None:
            thumb_h = h // 3
            ratio   = card_thumb.shape[1] / card_thumb.shape[0]
            thumb_w = int(thumb_h * ratio)
            thumb   = cv2.resize(card_thumb, (thumb_w, thumb_h))
            margin  = 10
            x1, y1  = w - thumb_w - margin, h - thumb_h - margin
            # fond semi-transparent
            roi = frame[y1:y1+thumb_h, x1:x1+thumb_w]
            frame[y1:y1+thumb_h, x1:x1+thumb_w] = cv2.addWeighted(roi, 0.2, thumb, 0.8, 0)
            cv2.rectangle(frame, (x1-2, y1-2), (x1+thumb_w+2, y1+thumb_h+2), color, 2)

        # --- Texte nom + distance ---
        if current_result:
            name = name_cache.get(current_result.uuid, current_result.uuid)
            line1 = name
            line2 = f"distance: {current_result.distance}/64  [{conf}]"
            cv2.putText(frame, line1, (BORDER+4, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2, cv2.LINE_AA)
            cv2.putText(frame, line2, (BORDER+4, 58),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)
        else:
            cv2.putText(frame, "Aucune carte detectee", (BORDER+4, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 1, cv2.LINE_AA)

        cv2.imshow("MTG Scanner", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    _cli_test()
