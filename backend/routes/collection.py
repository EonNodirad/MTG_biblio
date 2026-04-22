import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from database import get_db
from models import CollectionEntry
from schemas import CollectionEntryCreate, CollectionEntryUpdate, CollectionEntryOut
from mtgjson import loader
from mtgjson import loader

router = APIRouter(prefix="/collection", tags=["collection"])


@router.get("/", response_model=list[CollectionEntryOut])
def list_collection(db: Session = Depends(get_db)):
    return db.query(CollectionEntry).all()


@router.post("/", response_model=CollectionEntryOut, status_code=201)
def add_card(entry: CollectionEntryCreate, db: Session = Depends(get_db)):
    if not loader.get_card(entry.card_uuid):
        raise HTTPException(status_code=404, detail="Card UUID not found in MTGjson data")

    # Même carte + même foil + même état → on incrémente la quantité
    existing = db.query(CollectionEntry).filter(
        CollectionEntry.card_uuid == entry.card_uuid,
        CollectionEntry.foil      == (entry.foil or False),
        CollectionEntry.condition == (entry.condition or "NM"),
    ).first()

    if existing:
        existing.quantity += entry.quantity or 1
        db.commit()
        db.refresh(existing)
        return existing

    db_entry = CollectionEntry(**entry.model_dump())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@router.patch("/{entry_id}", response_model=CollectionEntryOut)
def update_card(entry_id: str, update: CollectionEntryUpdate, db: Session = Depends(get_db)):
    db_entry = db.get(CollectionEntry, entry_id)
    if db_entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    for field, value in update.model_dump(exclude_none=True).items():
        setattr(db_entry, field, value)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@router.delete("/{entry_id}", status_code=204)
def delete_card(entry_id: str, db: Session = Depends(get_db)):
    db_entry = db.get(CollectionEntry, entry_id)
    if db_entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(db_entry)
    db.commit()


@router.get("/missing/{set_code}")
def missing_cards(set_code: str, db: Session = Depends(get_db)):
    """Return cards from a set that are not in the collection."""
    set_data = loader.get_set(set_code)
    if set_data is None:
        raise HTTPException(status_code=404, detail="Set not found")

    # All cards in the set
    all_set_cards = loader.search_cards(set_code=set_code, limit=10000)
    owned_uuids = {e.card_uuid for e in db.query(CollectionEntry).all()}

    missing = [c for c in all_set_cards if c["uuid"] not in owned_uuids]
    return {"set": set_code, "total": len(all_set_cards), "missing_count": len(missing), "missing": missing}


@router.get("/export/csv", response_class=PlainTextResponse)
def export_collection_csv(db: Session = Depends(get_db)):
    entries = db.query(CollectionEntry).all()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["card_uuid", "name", "set", "quantity", "foil", "condition"])
    for e in entries:
        card = loader.get_card(e.card_uuid)
        name = card.get("name", "") if card else ""
        set_code = card.get("setCode", "") if card else ""
        w.writerow([e.card_uuid, name, set_code, e.quantity, "true" if e.foil else "false", e.condition])
    return PlainTextResponse(out.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=collection.csv"})


@router.post("/import/csv")
def import_collection_csv(
    body: str = Body(..., media_type="text/plain"),
    db: Session = Depends(get_db),
):
    reader = csv.DictReader(io.StringIO(body))
    imported, skipped = 0, []
    for row in reader:
        uuid = row.get("card_uuid", "").strip()
        if not uuid or not loader.get_card(uuid):
            skipped.append(uuid or str(row))
            continue
        try:
            qty = max(1, int(row.get("quantity", 1)))
            foil = row.get("foil", "false").lower() == "true"
            condition = row.get("condition", "NM").strip() or "NM"
            db_entry = CollectionEntry(card_uuid=uuid, quantity=qty, foil=foil, condition=condition)
            db.add(db_entry)
            imported += 1
        except Exception:
            skipped.append(uuid)
    db.commit()
    return {"imported": imported, "skipped": skipped}
