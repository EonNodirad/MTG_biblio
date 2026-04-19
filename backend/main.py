import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from database import Base, engine
from mtgjson import loader
from mtgjson import prices as price_loader
from routes import cards, collection, decks, stats, wishlist

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _price_refresh_loop() -> None:
    """Check every hour; re-download if file is older than PRICES_MAX_AGE_DAYS."""
    while True:
        await asyncio.sleep(3600)
        age = price_loader.prices_file_age_days()
        if age is None or age > price_loader.PRICES_MAX_AGE_DAYS:
            logger.info("Scheduled price refresh triggered (age=%s days)", age)
            await run_in_threadpool(price_loader.refresh_prices)


def _migrate_db() -> None:
    """Add category column and migrate from is_sideboard if needed."""
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE deck_entries ADD COLUMN category VARCHAR DEFAULT 'mainboard'"))
            conn.execute(text(
                "UPDATE deck_entries SET category = CASE WHEN is_sideboard = 1 THEN 'sideboard' ELSE 'mainboard' END"
            ))
            conn.commit()
            logger.info("Migrated deck_entries: is_sideboard → category")
        except Exception:
            pass  # Column already exists


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _migrate_db()
    loader.load_data()
    price_loader.load_prices()
    task = asyncio.create_task(_price_refresh_loop())
    yield
    task.cancel()


app = FastAPI(title="MTG Collection Manager", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cards.router)
app.include_router(collection.router)
app.include_router(decks.router)
app.include_router(stats.router)
app.include_router(wishlist.router)


@app.get("/")
def root():
    return {
        "status": "ok",
        "mtgjson_loaded": loader.is_loaded(),
    }
