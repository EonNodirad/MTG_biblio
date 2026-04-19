"""
Loads the latest card prices from MTGjson AllPrices.json.xz.

Keeps only the most recent price per UUID in a compact in-memory dict:
  _prices[uuid] = {"eur": float|None, "eur_foil": float|None,
                   "usd": float|None, "usd_foil": float|None}
"""

import json
import logging
import lzma
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DATA_DIR    = Path(__file__).parent.parent / "data"
PRICES_FILE = DATA_DIR / "AllPrices.json.xz"
PRICES_URL  = "https://mtgjson.com/api/v5/AllPrices.json.xz"

PRICES_MAX_AGE_DAYS = 7

_prices: dict[str, dict] = {}


def is_loaded() -> bool:
    return len(_prices) > 0


def prices_file_age_days() -> Optional[float]:
    if not PRICES_FILE.exists():
        return None
    return (time.time() - PRICES_FILE.stat().st_mtime) / 86400


def has_internet() -> bool:
    try:
        httpx.get("https://mtgjson.com", timeout=5, follow_redirects=True)
        return True
    except Exception:
        return False


def download_prices() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading MTGjson AllPrices.json.xz …")
    with httpx.Client(timeout=600, follow_redirects=True,
                      headers={"User-Agent": "MTGCollectionManager/1.0"}) as client:
        with client.stream("GET", PRICES_URL) as r:
            r.raise_for_status()
            with open(PRICES_FILE, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)
    logger.info("Prices file saved to %s", PRICES_FILE)


def _latest(date_map: dict) -> Optional[float]:
    """Return the value for the most recent date key, or None."""
    if not date_map:
        return None
    latest_key = max(date_map.keys())
    val = date_map[latest_key]
    return float(val) if val is not None else None


def _parse_file() -> None:
    global _prices
    logger.info("Parsing AllPrices.json.xz (this may take a minute)…")
    with lzma.open(PRICES_FILE, "rt", encoding="utf-8") as f:
        raw = json.load(f)

    data = raw.get("data", {})
    result: dict[str, dict] = {}

    for uuid, providers in data.items():
        paper = providers.get("paper", {})
        eur = eur_foil = usd = usd_foil = None

        cm = paper.get("cardmarket", {}).get("retail", {})
        if cm:
            eur      = _latest(cm.get("normal", {}))
            eur_foil = _latest(cm.get("foil", {}))

        tcp = paper.get("tcgplayer", {}).get("retail", {})
        if tcp:
            usd      = _latest(tcp.get("normal", {}))
            usd_foil = _latest(tcp.get("foil", {}))

        if any(v is not None for v in (eur, eur_foil, usd, usd_foil)):
            result[uuid] = {"eur": eur, "eur_foil": eur_foil,
                            "usd": usd, "usd_foil": usd_foil}

    _prices = result
    logger.info("Prices loaded for %d cards", len(_prices))


def load_prices() -> None:
    age = prices_file_age_days()
    if age is None:
        # File missing — download if we can
        if has_internet():
            download_prices()
        else:
            logger.warning("AllPrices.json.xz missing and no internet — prices unavailable")
            return
    elif age > PRICES_MAX_AGE_DAYS:
        # Stale — refresh if we can, otherwise use existing file
        logger.info("Prices file is %.1f days old — refreshing…", age)
        if has_internet():
            PRICES_FILE.unlink(missing_ok=True)
            download_prices()
        else:
            logger.warning("Prices file is stale but no internet — using existing file")

    if PRICES_FILE.exists():
        _parse_file()


def refresh_prices() -> dict:
    """Force re-download and reload regardless of file age."""
    if not has_internet():
        logger.warning("Price refresh requested but no internet connection")
        return {"success": False, "reason": "no_internet"}
    PRICES_FILE.unlink(missing_ok=True)
    download_prices()
    _parse_file()
    return {"success": True, "card_count": len(_prices)}


def get_price(uuid: str) -> Optional[dict]:
    return _prices.get(uuid)


def get_prices_bulk(uuids: list[str]) -> dict[str, dict]:
    return {u: _prices[u] for u in uuids if u in _prices}
