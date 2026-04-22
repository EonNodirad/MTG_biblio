from pydantic import BaseModel
from typing import Optional


# --- Collection ---

class CollectionEntryCreate(BaseModel):
    card_uuid: str
    quantity: int = 1
    foil: bool = False
    condition: str = "NM"


class CollectionEntryUpdate(BaseModel):
    quantity: Optional[int] = None
    foil: Optional[bool] = None
    condition: Optional[str] = None
    card_uuid: Optional[str] = None


class CollectionEntryOut(BaseModel):
    id: str
    card_uuid: str
    quantity: int
    foil: bool
    condition: str

    model_config = {"from_attributes": True}


# --- Decks ---

class DeckCreate(BaseModel):
    name: str
    description: str = ""
    format: str = ""
    colors: str = ""


class DeckUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    format: Optional[str] = None
    colors: Optional[str] = None


class DeckEntryCreate(BaseModel):
    card_uuid: str
    quantity: int = 1
    category: str = "mainboard"  # mainboard, sideboard, commander, companion, maybeboard


class DeckEntryOut(BaseModel):
    id: str
    card_uuid: str
    quantity: int
    category: str

    model_config = {"from_attributes": True}


class DeckOut(BaseModel):
    id: str
    name: str
    description: str
    format: str
    colors: str = ""
    entries: list[DeckEntryOut] = []

    model_config = {"from_attributes": True}
