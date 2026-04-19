import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from mtgjson import prices as price_loader
from sqlalchemy.orm import Session
from database import get_db
from models import Deck, DeckEntry, CollectionEntry
from schemas import DeckCreate, DeckUpdate, DeckEntryCreate, DeckOut, DeckEntryOut
from mtgjson import loader

router = APIRouter(prefix="/decks", tags=["decks"])

RESERVED = {"mainboard", "sideboard", "commander", "companion", "maybeboard"}

def _valid_category(cat: str) -> bool:
    return bool(cat and cat.strip())


# ---------------------------------------------------------------------------
# Decks CRUD
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[DeckOut])
def list_decks(db: Session = Depends(get_db)):
    return db.query(Deck).all()


@router.post("/", response_model=DeckOut, status_code=201)
def create_deck(deck: DeckCreate, db: Session = Depends(get_db)):
    db_deck = Deck(**deck.model_dump())
    db.add(db_deck)
    db.commit()
    db.refresh(db_deck)
    return db_deck


@router.get("/{deck_id}", response_model=DeckOut)
def get_deck(deck_id: str, db: Session = Depends(get_db)):
    deck = db.get(Deck, deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="Deck not found")
    return deck


@router.patch("/{deck_id}", response_model=DeckOut)
def update_deck(deck_id: str, update: DeckUpdate, db: Session = Depends(get_db)):
    deck = db.get(Deck, deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="Deck not found")
    for field, value in update.model_dump(exclude_none=True).items():
        setattr(deck, field, value)
    db.commit()
    db.refresh(deck)
    return deck


@router.delete("/{deck_id}", status_code=204)
def delete_deck(deck_id: str, db: Session = Depends(get_db)):
    deck = db.get(Deck, deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="Deck not found")
    db.delete(deck)
    db.commit()


# ---------------------------------------------------------------------------
# Deck entries
# ---------------------------------------------------------------------------

@router.post("/{deck_id}/cards", response_model=DeckEntryOut, status_code=201)
def add_card_to_deck(deck_id: str, entry: DeckEntryCreate, db: Session = Depends(get_db)):
    deck = db.get(Deck, deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="Deck not found")
    if not loader.get_card(entry.card_uuid):
        raise HTTPException(status_code=404, detail="Card UUID not found in MTGjson data")
    if not _valid_category(entry.category):
        raise HTTPException(status_code=400, detail="Category must be a non-empty string")
    db_entry = DeckEntry(deck_id=deck_id, **entry.model_dump())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


class DeckEntryUpdate(BaseModel):
    quantity: Optional[int] = None
    category: Optional[str] = None


@router.patch("/{deck_id}/cards/{entry_id}", response_model=DeckEntryOut)
def update_deck_entry(deck_id: str, entry_id: str, update: DeckEntryUpdate, db: Session = Depends(get_db)):
    entry = db.get(DeckEntry, entry_id)
    if entry is None or entry.deck_id != deck_id:
        raise HTTPException(status_code=404, detail="Entry not found")
    if update.quantity is not None:
        if update.quantity <= 0:
            db.delete(entry)
            db.commit()
            raise HTTPException(status_code=204, detail="Entry deleted")
        entry.quantity = update.quantity
    if update.category is not None:
        if not _valid_category(update.category):
            raise HTTPException(status_code=400, detail="Category must be a non-empty string")
        entry.category = update.category
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{deck_id}/cards/{entry_id}", status_code=204)
def remove_card_from_deck(deck_id: str, entry_id: str, db: Session = Depends(get_db)):
    entry = db.get(DeckEntry, entry_id)
    if entry is None or entry.deck_id != deck_id:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()


# ---------------------------------------------------------------------------
# Export deck to text (MTGA / Moxfield format)
# ---------------------------------------------------------------------------

@router.get("/{deck_id}/export", response_class=PlainTextResponse)
def export_deck_text(deck_id: str, db: Session = Depends(get_db)):
    deck = db.get(Deck, deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="Deck not found")

    def card_line(entry: DeckEntry) -> str:
        card = loader.get_card(entry.card_uuid)
        name = card.get("name", entry.card_uuid) if card else entry.card_uuid
        set_code = card.get("setCode", "") if card else ""
        return f"{entry.quantity} {name} ({set_code})" if set_code else f"{entry.quantity} {name}"

    sections: list[tuple[str, list[DeckEntry]]] = [
        ("", [e for e in deck.entries if e.category == "mainboard"]),
        ("Commander", [e for e in deck.entries if e.category == "commander"]),
        ("Companion", [e for e in deck.entries if e.category == "companion"]),
        ("Sideboard", [e for e in deck.entries if e.category == "sideboard"]),
        ("Maybeboard", [e for e in deck.entries if e.category == "maybeboard"]),
    ]

    lines: list[str] = []
    for header, entries in sections:
        if not entries:
            continue
        if header:
            lines.append("")
            lines.append(header)
        for entry in entries:
            lines.append(card_line(entry))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Import deck from text (MTGA / Moxfield format)
# ---------------------------------------------------------------------------

_LINE_RE = re.compile(
    r"^(\d+)\s+(.+?)(?:\s+\(([A-Z0-9]+)\)(?:\s+\d+)?)?$"
)
_SECTION_HEADERS = {"deck", "sideboard", "commander", "companion", "maybeboard"}


class ImportResult(BaseModel):
    imported: int
    skipped: list[str]


@router.post("/{deck_id}/import", response_model=ImportResult)
def import_deck_text(
    deck_id: str,
    body: str = Body(..., media_type="text/plain"),
    db: Session = Depends(get_db),
):
    deck = db.get(Deck, deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="Deck not found")

    current_category = "mainboard"
    imported = 0
    skipped: list[str] = []

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lower = line.lower()
        if lower in _SECTION_HEADERS:
            current_category = lower if lower != "deck" else "mainboard"
            continue

        m = _LINE_RE.match(line)
        if not m:
            skipped.append(line)
            continue

        quantity = int(m.group(1))
        name     = m.group(2).strip()
        set_hint = m.group(3)

        matches = loader.find_cards_by_name(name, set_hint)
        if not matches:
            skipped.append(f"{quantity} {name}")
            continue

        card_uuid = matches[0]["uuid"]
        db_entry = DeckEntry(
            deck_id=deck_id,
            card_uuid=card_uuid,
            quantity=quantity,
            category=current_category,
        )
        db.add(db_entry)
        imported += 1

    db.commit()
    return {"imported": imported, "skipped": skipped}


# ---------------------------------------------------------------------------
# Feasibility
# ---------------------------------------------------------------------------

@router.get("/{deck_id}/feasibility")
def deck_feasibility(deck_id: str, db: Session = Depends(get_db)):
    deck = db.get(Deck, deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="Deck not found")

    # Build both UUID-based and name-based ownership maps
    # (same card can have different UUIDs across printings)
    owned_by_uuid: dict[str, int] = {}
    owned_by_name: dict[str, int] = {}
    for e in db.query(CollectionEntry).all():
        owned_by_uuid[e.card_uuid] = owned_by_uuid.get(e.card_uuid, 0) + e.quantity
        col_card = loader.get_card(e.card_uuid)
        if col_card:
            name = col_card.get("name", "")
            if name:
                owned_by_name[name] = owned_by_name.get(name, 0) + e.quantity

    owned_cards, missing_cards = [], []
    for entry in deck.entries:
        if entry.category == "maybeboard":
            continue
        card = loader.get_card(entry.card_uuid)
        card_name = card.get("name") if card else None
        # Match by name across all printings, fallback to exact UUID
        qty_owned = owned_by_name.get(card_name, 0) if card_name else owned_by_uuid.get(entry.card_uuid, 0)
        info = {
            "card_uuid": entry.card_uuid,
            "name": card_name or entry.card_uuid,
            "needed": entry.quantity,
            "owned": qty_owned,
            "category": entry.category,
        }
        if qty_owned >= entry.quantity:
            owned_cards.append(info)
        else:
            info["missing"] = entry.quantity - qty_owned
            missing_cards.append(info)

    return {
        "deck_id": deck_id,
        "feasible": len(missing_cards) == 0,
        "owned": owned_cards,
        "missing": missing_cards,
    }


@router.get("/{deck_id}/price")
def deck_price(deck_id: str, db: Session = Depends(get_db)):
    deck = db.get(Deck, deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="Deck not found")

    total_eur = total_usd = 0.0
    entries_with_price = []
    for entry in deck.entries:
        if entry.category == "maybeboard":
            continue
        p = price_loader.get_price(entry.card_uuid)
        eur = (p.get("eur") or 0) * entry.quantity if p else 0
        usd = (p.get("usd") or 0) * entry.quantity if p else 0
        total_eur += eur
        total_usd += usd
        entries_with_price.append({
            "card_uuid": entry.card_uuid,
            "quantity": entry.quantity,
            "category": entry.category,
            "eur": p.get("eur") if p else None,
            "usd": p.get("usd") if p else None,
        })

    return {
        "deck_id": deck_id,
        "total_eur": round(total_eur, 2),
        "total_usd": round(total_usd, 2),
        "entries": entries_with_price,
    }
