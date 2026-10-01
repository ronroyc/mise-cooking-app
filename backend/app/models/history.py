"""Database table for cooking history: what was cooked, when, and how it turned out.

    recipes ──< cooking_logs

Deleting a recipe keeps its history: recipe_id becomes NULL and recipe_title
still says what it was.
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base
from app.models.recipe import Recipe, utc_now


class CookingLog(Base):
    __tablename__ = "cooking_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[Optional[int]] = mapped_column(ForeignKey("recipes.id", ondelete="SET NULL"))
    recipe_title: Mapped[str] = mapped_column(String(200))  # kept if the recipe is deleted
    cooked_on: Mapped[date] = mapped_column(Date)
    servings: Mapped[int]
    rating: Mapped[Optional[int]]  # 1-5, or None if not rated
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    recipe: Mapped[Optional[Recipe]] = relationship(back_populates="cook_logs")
