"""Database table for the kitchen inventory: what's in the pantry, fridge, and freezer.

    ingredients ──< inventory_items

Each inventory item points at the same `ingredients` row that recipes use, so
"do I have garlic?" is a simple id comparison later (Milestone 3).
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base
from app.models.recipe import Ingredient, utc_now

LOCATIONS = ("pantry", "fridge", "freezer")

# An item counts as "expiring soon" when it expires within this many days.
EXPIRING_SOON_DAYS = 3


def expiration_status(expiration_date: Optional[date], today: date) -> Optional[str]:
    """'expired', 'expiring_soon', 'fresh', or None when there's no date.

    `today` is passed in (instead of calling date.today() here) so tests can pick the date.
    """
    if expiration_date is None:
        return None
    days_left = (expiration_date - today).days
    if days_left < 0:
        return "expired"
    if days_left <= EXPIRING_SOON_DAYS:
        return "expiring_soon"
    return "fresh"


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    # unique: one row per ingredient, so "how much rice do I have?" has one answer.
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), unique=True)
    quantity: Mapped[Optional[float]]  # None means "some" (amount not tracked)
    unit: Mapped[Optional[str]] = mapped_column(String(20))
    location: Mapped[str] = mapped_column(String(20), default="pantry")
    expiration_date: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    ingredient: Mapped[Ingredient] = relationship()

    @property
    def name(self) -> str:
        return self.ingredient.name

    @property
    def category(self) -> Optional[str]:
        return self.ingredient.category

    @property
    def days_until_expiration(self) -> Optional[int]:
        if self.expiration_date is None:
            return None
        return (self.expiration_date - date.today()).days

    @property
    def expiration_status(self) -> Optional[str]:
        return expiration_status(self.expiration_date, date.today())
