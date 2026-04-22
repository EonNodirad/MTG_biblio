import asyncio
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from database import get_db
from models import CollectionEntry, Deck
from mtgjson import loader
from mtgjson import prices as price_loader
import card_scanner

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/")
def get_stats(db: Session = Depends(get_db)):
    collection = db.query(CollectionEntry).all()
    total_cards = sum(e.quantity for e in collection)
    unique_cards = len(collection)
    foil_count = sum(e.quantity for e in collection if e.foil)

    # Color distribution (by quantity owned)
    color_counts: dict[str, int] = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0}
    rarity_counts: dict[str, int] = {'mythic': 0, 'rare': 0, 'uncommon': 0, 'common': 0}
    for entry in collection:
        card = loader.get_card(entry.card_uuid)
        if not card:
            continue
        for color in (card.get('colors') or []):
            if color in color_counts:
                color_counts[color] += entry.quantity
        rarity = card.get('rarity', '')
        if rarity in rarity_counts:
            rarity_counts[rarity] += entry.quantity

    # Collection value
    collection_eur = collection_usd = 0.0
    for e in collection:
        p = price_loader.get_price(e.card_uuid)
        if p:
            eur_key = "eur_foil" if e.foil else "eur"
            usd_key = "usd_foil" if e.foil else "usd"
            collection_eur += (p.get(eur_key) or p.get("eur") or 0) * e.quantity
            collection_usd += (p.get(usd_key) or p.get("usd") or 0) * e.quantity

    decks = db.query(Deck).all()
    deck_list = [
        {
            'id': d.id,
            'name': d.name,
            'format': d.format or '',
            'description': d.description or '',
            'card_count': sum(e.quantity for e in d.entries if e.category not in ('sideboard', 'maybeboard')),
        }
        for d in decks
    ]

    # Set completion — efficient: 2 SQL queries on MTGjson DB
    owned_uuids = [e.card_uuid for e in collection]
    set_completion: list[dict] = []
    if owned_uuids:
        with loader._conn() as c:
            placeholders = ','.join('?' * len(owned_uuids))
            uuid_sets = c.execute(
                f"SELECT uuid, setCode FROM cards WHERE uuid IN ({placeholders})",
                owned_uuids,
            ).fetchall()
            owned_per_set: dict[str, int] = {}
            for row in uuid_sets:
                owned_per_set[row['setCode']] = owned_per_set.get(row['setCode'], 0) + 1

            set_codes = list(owned_per_set.keys())
            sp = ','.join('?' * len(set_codes))
            set_rows = c.execute(
                f"SELECT code, name, totalSetSize FROM sets WHERE code IN ({sp})",
                set_codes,
            ).fetchall()

        for row in set_rows:
            total = row['totalSetSize'] or 0
            owned = owned_per_set.get(row['code'], 0)
            if total > 0:
                set_completion.append({
                    'code': row['code'],
                    'name': row['name'],
                    'owned': owned,
                    'total': total,
                    'pct': round(owned / total * 100, 1),
                })
        set_completion.sort(key=lambda x: (-x['pct'], -x['owned']))

    return {
        'total_cards': total_cards,
        'unique_cards': unique_cards,
        'foil_count': foil_count,
        'color_distribution': color_counts,
        'rarity_distribution': rarity_counts,
        'total_decks': len(decks),
        'decks': deck_list,
        'set_completion': set_completion[:20],
        'collection_eur': round(collection_eur, 2),
        'collection_usd': round(collection_usd, 2),
        'prices_loaded': price_loader.is_loaded(),
        'prices_file_age_days': price_loader.prices_file_age_days(),
        'data_file_age_days': loader.loader_file_age_days(),
    }


@router.post("/refresh-prices")
async def refresh_prices():
    result = await run_in_threadpool(price_loader.refresh_prices)
    return {
        **result,
        "prices_loaded": price_loader.is_loaded(),
        "card_count": len(price_loader._prices),
    }


@router.post("/refresh-data")
async def refresh_data():
    result = await run_in_threadpool(loader.refresh_data)
    if result.get("success"):
        # Rebuild scanner index in background (incremental — new cards only)
        asyncio.create_task(run_in_threadpool(card_scanner.rebuild_index_incremental))
    return {
        **result,
        "data_loaded": loader.is_loaded(),
        "data_file_age_days": loader.loader_file_age_days(),
    }
