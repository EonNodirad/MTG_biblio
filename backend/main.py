import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

from database import Base, engine
from mtgjson import loader
from mtgjson import prices as price_loader
import card_scanner
from routes import cards, collection, decks, stats, wishlist, scan

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent / "frontend_build"


async def _price_refresh_loop() -> None:
    while True:
        await asyncio.sleep(3600)
        age = price_loader.prices_file_age_days()
        if age is None or age > price_loader.PRICES_MAX_AGE_DAYS:
            logger.info("Scheduled price refresh triggered (age=%s days)", age)
            await run_in_threadpool(price_loader.refresh_prices)


async def _data_refresh_loop() -> None:
    while True:
        await asyncio.sleep(3600)
        age = loader.loader_file_age_days()
        if age is None or age > loader.DATA_MAX_AGE_DAYS:
            logger.info("Scheduled data refresh triggered (age=%s days)", age)
            result = await run_in_threadpool(loader.refresh_data)
            if result.get("success"):
                # Rebuild scanner index incrementally (new cards only)
                await run_in_threadpool(card_scanner.rebuild_index_incremental)


def _migrate_db() -> None:
    with engine.connect() as conn:
        for sql in [
            "ALTER TABLE deck_entries ADD COLUMN category VARCHAR DEFAULT 'mainboard'",
            "UPDATE deck_entries SET category = CASE WHEN is_sideboard = 1 THEN 'sideboard' ELSE 'mainboard' END",
            "ALTER TABLE decks ADD COLUMN colors VARCHAR DEFAULT ''",
        ]:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass


def _initial_load() -> None:
    """Chargement initial en thread séparé — ne bloque pas le démarrage du serveur."""
    loader.load_data()
    price_loader.load_prices()
    card_scanner.load_scanner()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _migrate_db()
    # Lancement en arrière-plan : le serveur démarre immédiatement
    task_init   = asyncio.create_task(run_in_threadpool(_initial_load))
    task_prices = asyncio.create_task(_price_refresh_loop())
    task_data   = asyncio.create_task(_data_refresh_loop())
    yield
    task_init.cancel()
    task_prices.cancel()
    task_data.cancel()


app = FastAPI(title="MTG Collection Manager", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tous les routers sous /api
app.include_router(cards.router,      prefix="/api")
app.include_router(collection.router, prefix="/api")
app.include_router(decks.router,      prefix="/api")
app.include_router(stats.router,      prefix="/api")
app.include_router(wishlist.router,   prefix="/api")
app.include_router(scan.router,       prefix="/api")


_NEEDS_MTGJSON = ("/api/cards/", "/api/stats/", "/api/scan/")

@app.middleware("http")
async def loading_guard(request: Request, call_next):
    """Retourne 503 uniquement pour les routes qui nécessitent MTGjson."""
    path = request.url.path
    needs = any(path.startswith(p) for p in _NEEDS_MTGJSON)
    if needs and not loader.is_loaded():
        return JSONResponse(
            {"detail": "Données en cours de chargement, veuillez patienter…"},
            status_code=503,
        )
    return await call_next(request)


@app.get("/api/health")
def health():
    return {"status": "ok", "mtgjson_loaded": loader.is_loaded()}


# Sert le frontend SPA (doit être en dernier)
if FRONTEND_DIR.exists():
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str, request: Request):
        file = FRONTEND_DIR / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(FRONTEND_DIR / "index.html")
