"""
MTGjson SQLite loader.

Downloads AllPrintings.sqlite from mtgjson.com on first run.
All card data is queried on-demand — nothing is loaded into RAM at startup
except a lightweight name index used for autocomplete suggestions.
"""

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
DB_FILE  = DATA_DIR / "AllPrintings.sqlite"
DATA_MAX_AGE_DAYS = 7
MTGJSON_URL = "https://mtgjson.com/api/v5/AllPrintings.sqlite"

# Lightweight in-memory suggest index built at startup:
# list of (lower_name, entry_dict) sorted alphabetically.
# entry_dict keys: uuid, name, setCode, scryfallId, language, foreignName
_suggest_index: list[tuple[str, dict]] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_FILE)
    c.row_factory = sqlite3.Row
    # SQLite LOWER() is ASCII-only; this handles accented characters (é→é, É→é, etc.)
    c.create_function("PYLOWER", 1, lambda s: s.casefold() if s else s)
    return c


def _split(value: Optional[str]) -> list[str]:
    """Split a comma-separated SQLite field into a Python list."""
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _parse_fd_identifiers(raw: Optional[str]) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _row_to_card(row: sqlite3.Row) -> dict:
    """Convert a `cards` row to a clean dict with parsed list fields."""
    d = dict(row)
    for field in ("colors", "colorIdentity", "keywords", "subtypes", "supertypes", "types"):
        d[field] = _split(d.get(field))
    return d


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def download_data() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DB_FILE.with_suffix(".tmp")
    logger.info("Downloading MTGjson AllPrintings.sqlite (~500 MB)…")
    try:
        with httpx.Client(timeout=600, follow_redirects=True,
                          headers={"User-Agent": "MTGCollectionManager/1.0"}) as client:
            with client.stream("GET", MTGJSON_URL) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=1024 * 1024):
                        f.write(chunk)
        tmp.replace(DB_FILE)  # atomic rename — l'ancien fichier reste lisible jusqu'au bout
        logger.info("SQLite saved to %s", DB_FILE)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _ensure_indexes() -> None:
    """Create search indexes if missing (runs once after first download)."""
    with _conn() as c:
        c.execute("CREATE INDEX IF NOT EXISTS idx_cards_name    ON cards(name COLLATE NOCASE)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cards_set     ON cards(setCode)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_fd_name       ON cardForeignData(name COLLATE NOCASE)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_fd_uuid       ON cardForeignData(uuid)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ci_uuid       ON cardIdentifiers(uuid)")
        c.commit()
    logger.info("Search indexes ready.")


def _build_suggest_index() -> None:
    """Load only the fields needed for autocomplete into RAM."""
    global _suggest_index
    entries: list[tuple[str, dict]] = []

    with _conn() as c:
        # English names
        for row in c.execute(
            "SELECT c.uuid, c.name, c.setCode, i.scryfallId "
            "FROM cards c LEFT JOIN cardIdentifiers i ON c.uuid = i.uuid"
        ):
            entries.append((
                row["name"].lower(),
                {"uuid": row["uuid"], "name": row["name"], "setCode": row["setCode"],
                 "scryfallId": row["scryfallId"], "language": "", "foreignName": None},
            ))

        # Foreign names
        for row in c.execute(
            "SELECT f.uuid, f.name AS foreignName, f.language, f.identifiers, "
            "       c.name, c.setCode, i.scryfallId "
            "FROM cardForeignData f "
            "JOIN cards c ON f.uuid = c.uuid "
            "LEFT JOIN cardIdentifiers i ON c.uuid = i.uuid"
        ):
            fd_ids = _parse_fd_identifiers(row["identifiers"])
            scryfall = fd_ids.get("scryfallId") or row["scryfallId"]
            entries.append((
                row["foreignName"].lower(),
                {"uuid": row["uuid"], "name": row["name"], "setCode": row["setCode"],
                 "scryfallId": scryfall, "language": row["language"],
                 "foreignName": row["foreignName"]},
            ))

    _suggest_index = sorted(entries, key=lambda x: x[0])
    logger.info("Suggest index: %d entries", len(_suggest_index))


def loader_file_age_days() -> Optional[float]:
    if not DB_FILE.exists():
        return None
    return (time.time() - DB_FILE.stat().st_mtime) / 86400


def has_internet() -> bool:
    try:
        httpx.get("https://mtgjson.com", timeout=5, follow_redirects=True)
        return True
    except Exception:
        return False


def _is_valid() -> bool:
    """Check that the SQLite file is a real AllPrintings DB (has the cards table)."""
    try:
        with _conn() as c:
            c.execute("SELECT 1 FROM cards LIMIT 1")
        return True
    except Exception:
        return False


def load_data() -> None:
    age = loader_file_age_days()
    needs_download = age is None

    if not needs_download and not _is_valid():
        logger.warning("AllPrintings.sqlite is corrupted — re-downloading…")
        DB_FILE.unlink(missing_ok=True)
        needs_download = True

    if needs_download or age is not None and age > DATA_MAX_AGE_DAYS:
        if needs_download:
            logger.info("AllPrintings.sqlite missing or corrupted — downloading…")
        else:
            logger.info("AllPrintings.sqlite is %.1f days old — refreshing…", age)
        if has_internet():
            DB_FILE.unlink(missing_ok=True)
            download_data()
        elif needs_download:
            logger.warning("AllPrintings.sqlite unavailable and no internet — card data unavailable")
            return
        else:
            logger.warning("AllPrintings.sqlite is stale but no internet — using existing file")

    _ensure_indexes()
    _build_suggest_index()
    logger.info("MTGjson SQLite ready.")


def refresh_data() -> dict:
    """Force re-download and rebuild of AllPrintings.sqlite."""
    if not has_internet():
        return {"success": False, "reason": "no_internet"}
    DB_FILE.unlink(missing_ok=True)
    download_data()
    _ensure_indexes()
    _build_suggest_index()
    return {"success": True}


def is_loaded() -> bool:
    return len(_suggest_index) > 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_card(uuid: str) -> Optional[dict]:
    """Return full card data for a UUID, including identifiers and foreignData."""
    with _conn() as c:
        row = c.execute("SELECT * FROM cards WHERE uuid = ?", (uuid,)).fetchone()
        if not row:
            return None
        card = _row_to_card(row)

        # Identifiers
        id_row = c.execute(
            "SELECT scryfallId FROM cardIdentifiers WHERE uuid = ?", (uuid,)
        ).fetchone()
        card["identifiers"] = {"scryfallId": id_row["scryfallId"] if id_row else None}

        # Foreign data
        fd_rows = c.execute(
            "SELECT language, name, text, type, flavorText, identifiers "
            "FROM cardForeignData WHERE uuid = ?",
            (uuid,),
        ).fetchall()
        card["foreignData"] = [
            {
                "language":   r["language"],
                "name":       r["name"],
                "text":       r["text"],
                "type":       r["type"],
                "flavorText": r["flavorText"],
                "identifiers": _parse_fd_identifiers(r["identifiers"]),
            }
            for r in fd_rows
        ]

        # Legalities
        leg_row = c.execute(
            "SELECT * FROM cardLegalities WHERE uuid = ?", (uuid,)
        ).fetchone()
        if leg_row:
            card["legalities"] = {k: v for k, v in dict(leg_row).items() if k != "uuid" and v}
        else:
            card["legalities"] = {}

        # Prices not available in AllPrintings.sqlite
        card["prices"] = None

    return card


def _card_summary(row: sqlite3.Row,
                  matched_foreign: Optional[str] = None,
                  matched_language: Optional[str] = None) -> dict:
    return {
        "uuid":               row["uuid"],
        "name":               row["name"],
        "setCode":            row["setCode"],
        "type":               row["type"],
        "manaCost":           row["manaCost"],
        "manaValue":          row["manaValue"],
        "colors":             row["colors"],
        "rarity":             row["rarity"],
        "scryfallId":         row["scryfallId"],
        "matchedForeignName": matched_foreign,
        "matchedLanguage":    matched_language,
    }


_COLOR_ORDER = "WUBRG"

_VALID_FORMATS = {
    "standard", "pioneer", "modern", "legacy", "commander", "vintage",
    "pauper", "historic", "timeless", "brawl", "alchemy", "duel",
    "oldschool", "premodern", "gladiator", "oathbreaker", "paupercommander",
}


def search_cards(
    query: str = "",
    set_code: str = "",
    card_type: str = "",
    colors: str = "",
    color_match: str = "any",
    text_search: str = "",
    rarities: str = "",
    cmc_min: Optional[int] = None,
    cmc_max: Optional[int] = None,
    card_types: str = "",
    subtype: str = "",
    supertype: str = "",
    format_legality: str = "",
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Search cards by name (English + all translations) with optional filters."""
    q = f"%{query.casefold()}%" if query else None

    cond_parts: list[str] = []
    cond_params: list = []

    if set_code:
        cond_parts.append("c.setCode = ?")
        cond_params.append(set_code.upper())
    if card_type:
        cond_parts.append("PYLOWER(c.type) LIKE ?")
        cond_params.append(f"%{card_type.casefold()}%")
    if text_search:
        q_text = f"%{text_search.casefold()}%"
        cond_parts.append(
            "(PYLOWER(COALESCE(c.text,'')) LIKE ? "
            "OR EXISTS (SELECT 1 FROM cardForeignData fd "
            "WHERE fd.uuid = c.uuid AND PYLOWER(COALESCE(fd.text,'')) LIKE ?))"
        )
        cond_params.extend([q_text, q_text])
    if card_types:
        types_list = [t.strip() for t in card_types.split(",") if t.strip()]
        if types_list:
            sub = " OR ".join("PYLOWER(c.type) LIKE ?" for _ in types_list)
            cond_parts.append(f"({sub})")
            cond_params.extend(f"%{t.casefold()}%" for t in types_list)
    if subtype:
        cond_parts.append("PYLOWER(COALESCE(c.subtypes,'')) LIKE ?")
        cond_params.append(f"%{subtype.casefold()}%")
    if supertype:
        cond_parts.append("PYLOWER(COALESCE(c.supertypes,'')) LIKE ?")
        cond_params.append(f"%{supertype.casefold()}%")
    if format_legality and format_legality.lower() in _VALID_FORMATS:
        fmt = format_legality.lower()
        cond_parts.append(
            f"EXISTS (SELECT 1 FROM cardLegalities cl WHERE cl.uuid = c.uuid AND cl.{fmt} = 'Legal')"
        )
    if rarities:
        rar_list = [r.strip().lower() for r in rarities.split(",") if r.strip()]
        if rar_list:
            placeholders = ",".join("?" * len(rar_list))
            cond_parts.append(f"c.rarity IN ({placeholders})")
            cond_params.extend(rar_list)
    if cmc_min is not None:
        cond_parts.append("c.manaValue >= ?")
        cond_params.append(cmc_min)
    if cmc_max is not None:
        cond_parts.append("c.manaValue <= ?")
        cond_params.append(cmc_max)
    if colors:
        raw_colors = [c.strip().upper() for c in colors.split(",") if c.strip()]
        wants_colorless = "C" in raw_colors
        color_list = [c for c in raw_colors if c in _COLOR_ORDER]
        if wants_colorless and not color_list:
            cond_parts.append("(c.colors IS NULL OR c.colors = '')")
        elif color_list:
            if color_match == "any":
                sub = " OR ".join("c.colors LIKE ?" for _ in color_list)
                cond_parts.append(f"({sub})")
                cond_params.extend(f"%{col}%" for col in color_list)
            elif color_match == "all":
                for col in color_list:
                    cond_parts.append("c.colors LIKE ?")
                    cond_params.append(f"%{col}%")
            elif color_match == "exact":
                sorted_colors = sorted(color_list, key=lambda x: _COLOR_ORDER.index(x))
                cond_parts.append("c.colors = ?")
                cond_params.append(",".join(sorted_colors))
            elif color_match == "exclude":
                for col in color_list:
                    cond_parts.append("(c.colors IS NULL OR c.colors NOT LIKE ?)")
                    cond_params.append(f"%{col}%")

    base_where = ("WHERE " + " AND ".join(cond_parts)) if cond_parts else ""

    results: list[dict] = []
    seen: set[str] = set()
    sql_limit = offset + limit

    with _conn() as c:
        # --- English name search ---
        en_where = base_where
        en_params = list(cond_params)
        if q:
            en_where = (base_where + " AND " if base_where else "WHERE ") + "PYLOWER(c.name) LIKE ?"
            en_params.append(q)

        sql_en = (
            "SELECT c.uuid, c.name, c.setCode, c.type, c.manaCost, c.manaValue, c.colors, c.rarity, i.scryfallId "
            "FROM cards c LEFT JOIN cardIdentifiers i ON c.uuid = i.uuid "
            f"{en_where} "
            f"LIMIT {sql_limit}"
        )
        for row in c.execute(sql_en, en_params):
            if row["uuid"] not in seen:
                seen.add(row["uuid"])
                results.append(_card_summary(row))

        # --- Foreign name search (only when a query is given) ---
        if q and len(results) < sql_limit:
            fd_limit = sql_limit - len(results)
            fd_where = (base_where + " AND " if base_where else "WHERE ") + "PYLOWER(f.name) LIKE ?"
            fd_params = list(cond_params) + [q]
            sql_fd = (
                "SELECT c.uuid, c.name, c.setCode, c.type, c.manaCost, c.manaValue, c.colors, c.rarity, "
                "       i.scryfallId, f.name AS fName, f.language AS fLang "
                "FROM cardForeignData f "
                "JOIN cards c ON f.uuid = c.uuid "
                "LEFT JOIN cardIdentifiers i ON c.uuid = i.uuid "
                f"{fd_where} "
                f"LIMIT {fd_limit}"
            )
            for row in c.execute(sql_fd, fd_params):
                if row["uuid"] not in seen:
                    seen.add(row["uuid"])
                    results.append(_card_summary(row, row["fName"], row["fLang"]))

    page = results[offset: offset + limit]

    # Attach EUR price (best-effort, no extra SQL round-trip)
    from mtgjson import prices as price_loader  # lazy import to avoid circular
    uuids = [r["uuid"] for r in page]
    bulk_prices = price_loader.get_prices_bulk(uuids)
    for r in page:
        p = bulk_prices.get(r["uuid"])
        r["eur"] = p["eur"] if p else None

    return page


def suggest_cards(query: str, limit: int = 10) -> list[dict]:
    """Fast autocomplete: prefix matches first, then contains. Deduped by uuid."""
    if not query:
        return []
    q = query.lower()
    # Deduplicate by (display_name, language) so the same card name
    # from different printings appears only once in suggestions.
    seen: set[tuple[str, str]] = set()
    results: list[dict] = []

    def _dedup_key(e: dict) -> tuple[str, str]:
        return (e["foreignName"] or e["name"], e["language"])

    # Pass 1: prefix matches (the index is sorted so we can break early)
    for lower_name, entry in _suggest_index:
        if lower_name.startswith(q):
            key = _dedup_key(entry)
            if key not in seen:
                seen.add(key)
                results.append(entry)
                if len(results) >= limit:
                    return results
        elif results and not lower_name.startswith(q[0]):
            break

    # Pass 2: contains matches
    if len(results) < limit:
        for lower_name, entry in _suggest_index:
            if q in lower_name and not lower_name.startswith(q):
                key = _dedup_key(entry)
                if key not in seen:
                    seen.add(key)
                    results.append(entry)
                    if len(results) >= limit:
                        break

    return results


def find_cards_by_name(name: str, set_hint: Optional[str] = None) -> list[dict]:
    """Find cards by exact English name, optionally filtered by set code."""
    with _conn() as c:
        if set_hint:
            rows = c.execute(
                "SELECT c.uuid, c.name, c.setCode, c.type, c.manaCost, c.rarity, i.scryfallId "
                "FROM cards c LEFT JOIN cardIdentifiers i ON c.uuid = i.uuid "
                "WHERE c.name = ? AND c.setCode = ?",
                (name, set_hint.upper()),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT c.uuid, c.name, c.setCode, c.type, c.manaCost, c.rarity, i.scryfallId "
                "FROM cards c LEFT JOIN cardIdentifiers i ON c.uuid = i.uuid "
                "WHERE c.name = ?",
                (name,),
            ).fetchall()
    return [_card_summary(r) for r in rows]


def get_set(set_code: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM sets WHERE code = ?", (set_code.upper(),)).fetchone()
        return dict(row) if row else None


def list_sets() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT code, name, releaseDate, type, totalSetSize FROM sets ORDER BY releaseDate DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_prices(uuid: str) -> Optional[dict]:
    """Prices are not included in AllPrintings.sqlite."""
    return None


def get_printings(name: str) -> list[dict]:
    """Return all printings (editions) of a card by its English name, newest first."""
    with _conn() as c:
        rows = c.execute(
            "SELECT c.uuid, c.name, c.setCode, c.rarity, c.manaCost, "
            "       i.scryfallId, s.name AS setName, s.releaseDate "
            "FROM cards c "
            "LEFT JOIN cardIdentifiers i ON c.uuid = i.uuid "
            "LEFT JOIN sets s ON c.setCode = s.code "
            "WHERE c.name = ? "
            "ORDER BY s.releaseDate DESC",
            (name,),
        ).fetchall()
        return [dict(r) for r in rows]
