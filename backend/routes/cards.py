from fastapi import APIRouter, HTTPException, Query
from mtgjson import loader
from mtgjson import prices as price_loader

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/search")
def search_cards(
    q: str = Query(default="", description="Partial card name"),
    set: str = Query(default="", description="Set code (e.g. MH2)"),
    type: str = Query(default="", description="Type line filter (e.g. Creature)"),
    colors: str = Query(default="", description="Comma-separated colors: W,U,B,R,G,C"),
    color_match: str = Query(default="any", description="any|all|exact|exclude"),
    text: str = Query(default="", description="Rules text search"),
    rarity: str = Query(default="", description="Comma-separated: common,uncommon,rare,mythic"),
    cmc_min: int | None = Query(default=None, description="Minimum converted mana cost"),
    cmc_max: int | None = Query(default=None, description="Maximum converted mana cost"),
    types: str = Query(default="", description="Comma-separated card types (OR): Creature,Instant"),
    subtype: str = Query(default="", description="Subtype search: Zombie, Dragon, Wizard..."),
    supertype: str = Query(default="", description="Supertype search: Legendary, Basic, Snow..."),
    format: str = Query(default="", description="Format legality: standard,pioneer,modern,commander..."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    return loader.search_cards(
        query=q, set_code=set, card_type=type,
        colors=colors, color_match=color_match,
        text_search=text, rarities=rarity,
        cmc_min=cmc_min, cmc_max=cmc_max,
        card_types=types, subtype=subtype, supertype=supertype, format_legality=format,
        limit=limit, offset=offset,
    )


@router.get("/suggest")
def suggest_cards(
    q: str = Query(default="", description="Prefix or partial card name (English or any language)"),
    limit: int = Query(default=10, ge=1, le=20),
):
    return loader.suggest_cards(query=q, limit=limit)


@router.get("/sets")
def list_sets():
    return loader.list_sets()


@router.get("/printings")
def get_printings(name: str = Query(..., description="Exact English card name")):
    return loader.get_printings(name)


@router.get("/sets/{set_code}")
def get_set(set_code: str):
    s = loader.get_set(set_code)
    if s is None:
        raise HTTPException(status_code=404, detail="Set not found")
    return s


@router.get("/{uuid}")
def get_card(uuid: str):
    card = loader.get_card(uuid)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    card["prices"] = price_loader.get_price(uuid)
    return card


@router.get("/{uuid}/prices")
def get_prices(uuid: str):
    p = price_loader.get_price(uuid)
    if p is None:
        return {}
    return p
