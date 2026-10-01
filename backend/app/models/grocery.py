"""Database table for the grocery list.

    ingredients ──< grocery_items

Items point at the shared `ingredients` rows, so a bought item can go straight into
the inventory and match recipes. The same ingredient can appear twice only when the
amounts can't be added together (2 lb of flour and 1 cup of flour).
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base
from app.models.recipe import Ingredient, utc_now


class GroceryItem(Base):
    __tablename__ = "grocery_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"))
    quantity: Mapped[Optional[float]]  # None means "some" (e.g. salt for a "to taste")
    unit: Mapped[Optional[str]] = mapped_column(String(20))
    checked: Mapped[bool] = mapped_column(default=False)  # in the cart
    for_recipes: Mapped[Optional[str]] = mapped_column(Text)  # "Oyakodon, Chicken Fried Rice"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    ingredient: Mapped[Ingredient] = relationship()

    @property
    def name(self) -> str:
        return self.ingredient.name

    @property
    def category(self) -> Optional[str]:
        return self.ingredient.category
