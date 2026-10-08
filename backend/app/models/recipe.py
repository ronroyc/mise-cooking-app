"""Database tables for recipes and ingredients.

    recipes ──< recipe_ingredients >── ingredients

A recipe uses many ingredients, and an ingredient appears in many recipes
(a many-to-many relationship). The recipe_ingredients table sits in the middle:
each row says "this recipe uses this much of this ingredient".
"""
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    servings: Mapped[int]
    prep_time: Mapped[int]  # minutes
    cook_time: Mapped[int]  # minutes
    cuisine: Mapped[Optional[str]] = mapped_column(String(50))
    instructions: Mapped[str] = mapped_column(Text)  # one step per line
    pinned_at: Mapped[Optional[datetime]] = mapped_column(DateTime)  # None = not pinned
    photo_filename: Mapped[Optional[str]] = mapped_column(String(100))  # in data/photos (services/photos.py)
    source_url: Mapped[Optional[str]] = mapped_column(String(500))  # the website it was imported from
    # For recipes whose source gave no times or servings (TheMealDB, services/mealdb.py):
    # time_status None = times as written, "estimated" = added up from the steps,
    # "unknown" = no times anywhere (left out of time filters).
    time_status: Mapped[Optional[str]] = mapped_column(String(20))
    servings_estimated: Mapped[Optional[bool]]  # True = servings is a guess
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    # recipe.ingredients -> list of RecipeIngredient rows.
    # "delete-orphan" means: delete a recipe and its recipe_ingredients rows go with it.
    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeIngredient.id",
    )

    # Newest first. passive_deletes: let the database's ON DELETE SET NULL keep the history.
    cook_logs: Mapped[list["CookingLog"]] = relationship(  # noqa: F821 (defined in models/history.py)
        back_populates="recipe",
        passive_deletes=True,
        order_by="(CookingLog.cooked_on.desc(), CookingLog.id.desc())",
    )

    @property
    def times_cooked(self) -> int:
        return len(self.cook_logs)

    @property
    def last_cooked(self) -> Optional[date]:
        return self.cook_logs[0].cooked_on if self.cook_logs else None

    @property
    def average_rating(self) -> Optional[float]:
        ratings = [log.rating for log in self.cook_logs if log.rating is not None]
        return round(sum(ratings) / len(ratings), 1) if ratings else None

    @property
    def pinned(self) -> bool:
        return self.pinned_at is not None

    @property
    def photo_url(self) -> Optional[str]:
        return f"/api/photos/{self.photo_filename}" if self.photo_filename else None

    @property
    def base_servings(self) -> int:
        return self.servings

    @property
    def total_time(self) -> int:
        return self.prep_time + self.cook_time


class Ingredient(Base):
    """One row per distinct ingredient ("garlic", "soy sauce"), shared by all recipes."""

    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)  # stored lowercase
    category: Mapped[Optional[str]] = mapped_column(String(50))  # e.g. "Produce"

    recipe_links: Mapped[list["RecipeIngredient"]] = relationship(back_populates="ingredient")


class RecipeIngredient(Base):
    """The join table: how much of one ingredient one recipe needs."""

    __tablename__ = "recipe_ingredients"
    # A recipe can't list the same ingredient twice.
    __table_args__ = (UniqueConstraint("recipe_id", "ingredient_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"))
    quantity: Mapped[Optional[float]]  # None means "to taste"
    unit: Mapped[Optional[str]] = mapped_column(String(20))
    optional: Mapped[bool] = mapped_column(default=False)
    preparation_note: Mapped[Optional[str]] = mapped_column(String(200))  # e.g. "minced"

    recipe: Mapped["Recipe"] = relationship(back_populates="ingredients")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="recipe_links")

    # Shortcuts so the API can return a flat {"name": ..., "quantity": ...} object.
    @property
    def name(self) -> str:
        return self.ingredient.name

    @property
    def category(self) -> Optional[str]:
        return self.ingredient.category
