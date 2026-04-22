"""
Build a perceptual hash index of all MTG cards from Scryfall images.

Usage:
    python build_index.py [--workers 4] [--limit 1000]

Output:
    index.db  — SQLite with columns: uuid, scryfall_id, phash (64-bit int)

The script is resumable: already-indexed cards are skipped on re-run.
Scryfall rate limit: 10 req/s max — we stay well under with async + semaphore.
"""

import argparse
import asyncio
import logging
import sqlite3
import sys
from pathlib import Path

import httpx
import imagehash
from PIL import Image
import io

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).parent.parent / "backend" / "data" / "AllPrintings.sqlite"
INDEX_DB    = Path(__file__).parent / "index.db"
MTGJSON_DB  = _DEFAULT_DB  # peut être écrasé via --db

SCRYFALL_IMG = "https://cards.scryfall.io/normal/front/{a}/{b}/{scryfall_id}.jpg"
CONCURRENCY  = 8   # parallel downloads
RATE_LIMIT   = 10  # requests/second (Scryfall policy)


# ---------------------------------------------------------------------------
# Index DB
# ---------------------------------------------------------------------------

def open_index() -> sqlite3.Connection:
    conn = sqlite3.connect(INDEX_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS card_hashes (
            uuid        TEXT PRIMARY KEY,
            scryfall_id TEXT NOT NULL,
            phash       TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_phash ON card_hashes(phash)")
    conn.commit()
    return conn


def load_already_indexed(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT uuid FROM card_hashes")}


# ---------------------------------------------------------------------------
# MTGjson source
# ---------------------------------------------------------------------------

def load_cards(limit: int | None) -> list[tuple[str, str]]:
    """Return list of (uuid, scryfall_id) from AllPrintings.sqlite."""
    src = sqlite3.connect(MTGJSON_DB)
    sql = "SELECT uuid, scryfallId FROM cardIdentifiers WHERE scryfallId IS NOT NULL"
    if limit:
        sql += f" LIMIT {limit}"
    rows = src.execute(sql).fetchall()
    src.close()
    return rows


# ---------------------------------------------------------------------------
# Download + hash
# ---------------------------------------------------------------------------

def scryfall_url(scryfall_id: str) -> str:
    a, b = scryfall_id[0], scryfall_id[1]
    return SCRYFALL_IMG.format(a=a, b=b, scryfall_id=scryfall_id)


async def fetch_and_hash(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    rate_sem: asyncio.Semaphore,
    uuid: str,
    scryfall_id: str,
) -> tuple[str, str, int] | None:
    url = scryfall_url(scryfall_id)
    async with sem:
        async with rate_sem:
            try:
                r = await client.get(url, timeout=15)
                if r.status_code == 429:
                    await asyncio.sleep(2)
                    r = await client.get(url, timeout=15)
                if r.status_code != 200:
                    logger.warning("HTTP %s for %s", r.status_code, scryfall_id)
                    return None
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                w, h_px = img.size
                # Crop to art box only (unique per card, avoids frame bias)
                # Scryfall normal: ~488×680 — percentages work for any size
                art = img.crop((
                    int(w * 0.06),
                    int(h_px * 0.08),
                    int(w * 0.94),
                    int(h_px * 0.48),
                ))
                h = imagehash.phash(art, hash_size=8)
                return (uuid, scryfall_id, str(h))
            except Exception as e:
                logger.warning("Error %s for %s: %s", type(e).__name__, scryfall_id, e)
                return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def build(limit: int | None, workers: int) -> None:
    if not MTGJSON_DB.exists():
        logger.error("AllPrintings.sqlite not found at %s", MTGJSON_DB)
        sys.exit(1)

    conn = open_index()
    already = load_already_indexed(conn)
    logger.info("Already indexed: %d cards", len(already))

    all_cards = load_cards(limit)
    todo = [(uuid, sid) for uuid, sid in all_cards if uuid not in already]
    logger.info("To index: %d cards (total in DB: %d)", len(todo), len(all_cards))

    if not todo:
        logger.info("Nothing to do.")
        conn.close()
        return

    sem       = asyncio.Semaphore(workers)
    rate_sem  = asyncio.Semaphore(RATE_LIMIT)

    # Release RATE_LIMIT tokens per second
    async def refill():
        while True:
            await asyncio.sleep(1)
            for _ in range(RATE_LIMIT):
                try:
                    rate_sem.release()
                except ValueError:
                    pass

    done = 0
    batch: list[tuple[str, str, int]] = []
    BATCH_SIZE = 200

    async with httpx.AsyncClient(headers={"User-Agent": "MTGCollectionManager/1.0"}) as client:
        refill_task = asyncio.create_task(refill())
        # Pre-drain the rate semaphore so refill controls the pace
        for _ in range(RATE_LIMIT):
            await rate_sem.acquire()

        tasks = [
            asyncio.create_task(fetch_and_hash(client, sem, rate_sem, uuid, sid))
            for uuid, sid in todo
        ]

        for coro in asyncio.as_completed(tasks):
            result = await coro
            done += 1
            if result:
                batch.append(result)
            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    "INSERT OR IGNORE INTO card_hashes(uuid, scryfall_id, phash) VALUES (?,?,?)",
                    batch,
                )
                conn.commit()
                batch.clear()
            if done % 500 == 0 or done == len(tasks):
                logger.info("Progress: %d / %d (%.1f%%)", done, len(tasks), done / len(tasks) * 100)

        refill_task.cancel()

    if batch:
        conn.executemany(
            "INSERT OR IGNORE INTO card_hashes(uuid, scryfall_id, phash) VALUES (?,?,?)",
            batch,
        )
        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM card_hashes").fetchone()[0]
    logger.info("Done. Index now contains %d cards.", total)
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=CONCURRENCY, help="Parallel downloads")
    parser.add_argument("--limit",   type=int, default=None, help="Only index N cards (for testing)")
    parser.add_argument("--db",      type=Path, default=None, help="Path to AllPrintings.sqlite")
    args = parser.parse_args()
    if args.db:
        MTGJSON_DB = args.db
    asyncio.run(build(args.limit, args.workers))
