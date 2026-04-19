from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models import WishlistEntry, CollectionEntry
from mtgjson import loader

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


class WishlistEntryCreate(BaseModel):
    card_uuid: str
    quantity: int = 1
    notes: str = ""


class WishlistEntryUpdate(BaseModel):
    quantity: Optional[int] = None
    notes: Optional[str] = None


class WishlistEntryOut(BaseModel):
    id: str
    card_uuid: str
    quantity: int
    notes: str

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[WishlistEntryOut])
def list_wishlist(db: Session = Depends(get_db)):
    return db.query(WishlistEntry).all()


@router.post("/", response_model=WishlistEntryOut, status_code=201)
def add_to_wishlist(entry: WishlistEntryCreate, db: Session = Depends(get_db)):
    if not loader.get_card(entry.card_uuid):
        raise HTTPException(status_code=404, detail="Card UUID not found")
    db_entry = WishlistEntry(**entry.model_dump())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@router.patch("/{entry_id}", response_model=WishlistEntryOut)
def update_wishlist_entry(entry_id: str, update: WishlistEntryUpdate, db: Session = Depends(get_db)):
    entry = db.get(WishlistEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    for field, value in update.model_dump(exclude_none=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=204)
def remove_from_wishlist(entry_id: str, db: Session = Depends(get_db)):
    entry = db.get(WishlistEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()


@router.get("/check")
def check_wishlist(db: Session = Depends(get_db)):
    """Compare wishlist against collection — returns owned/missing per entry."""
    wishlist = db.query(WishlistEntry).all()
    owned_by_name: dict[str, int] = {}
    for e in db.query(CollectionEntry).all():
        card = loader.get_card(e.card_uuid)
        if card:
            name = card.get("name", "")
            if name:
                owned_by_name[name] = owned_by_name.get(name, 0) + e.quantity

    results = []
    for entry in wishlist:
        card = loader.get_card(entry.card_uuid)
        name = card.get("name") if card else entry.card_uuid
        scryfall_id = card.get("identifiers", {}).get("scryfallId") if card else None
        owned = owned_by_name.get(name, 0) if name else 0
        results.append({
            "id": entry.id,
            "card_uuid": entry.card_uuid,
            "name": name,
            "scryfallId": scryfall_id,
            "quantity": entry.quantity,
            "owned": owned,
            "missing": max(0, entry.quantity - owned),
            "notes": entry.notes,
        })

    return results
