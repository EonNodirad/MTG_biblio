import uuid as uuid_lib
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base


def new_uuid() -> str:
    return str(uuid_lib.uuid4())


class CollectionEntry(Base):
    __tablename__ = "collection"

    id = Column(String, primary_key=True, default=new_uuid)
    card_uuid = Column(String, nullable=False, index=True)  # MTGjson UUID
    quantity = Column(Integer, nullable=False, default=1)
    foil = Column(Boolean, default=False)
    condition = Column(String, default="NM")  # NM, LP, MP, HP, DMG


class Deck(Base):
    __tablename__ = "decks"

    id = Column(String, primary_key=True, default=new_uuid)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    format = Column(String, default="")  # standard, modern, commander...

    entries = relationship("DeckEntry", back_populates="deck", cascade="all, delete-orphan")


class DeckEntry(Base):
    __tablename__ = "deck_entries"

    id = Column(String, primary_key=True, default=new_uuid)
    deck_id = Column(String, ForeignKey("decks.id"), nullable=False)
    card_uuid = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    category = Column(String, default="mainboard")  # mainboard, sideboard, commander, companion, maybeboard

    deck = relationship("Deck", back_populates="entries")


class WishlistEntry(Base):
    __tablename__ = "wishlist"

    id = Column(String, primary_key=True, default=new_uuid)
    card_uuid = Column(String, nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    notes = Column(Text, default="")
