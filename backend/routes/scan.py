from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.concurrency import run_in_threadpool
import card_scanner
from card_scanner import get_scanner
from mtgjson import loader

router = APIRouter(prefix="/scan", tags=["scan"])


@router.post("/rebuild-index")
async def rebuild_index():
    result = await run_in_threadpool(card_scanner.rebuild_index_incremental)
    return result


@router.post("/")
async def scan_card(file: UploadFile = File(...)):
    scanner = get_scanner()
    if scanner is None:
        raise HTTPException(status_code=503, detail="Scanner index not loaded. Run ml/build_index.py first.")

    data   = await file.read()
    result = await run_in_threadpool(scanner.find, data)

    if result is None:
        raise HTTPException(status_code=400, detail="Cannot decode image.")

    card = loader.get_card(result.uuid) if result.confidence != "none" else None

    return {
        "uuid":        result.uuid,
        "scryfall_id": result.scryfall_id,
        "distance":    result.distance,
        "confidence":  result.confidence,
        "quad":        result.quad,
        "guide":       result.guide,  # [x1,y1,x2,y2] normalisé 0-1
        "name":        card["name"]     if card else None,
        "set_code":    card["setCode"]  if card else None,
        "type":        card["type"]     if card else None,
        "mana_cost":   card["manaCost"] if card else None,
        "rarity":      card["rarity"]   if card else None,
    }
