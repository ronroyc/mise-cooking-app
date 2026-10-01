"""Inventory business logic: reading and writing what's in the kitchen."""
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ingredient, InventoryItem
from app.models.recipe import utc_now
from app.schemas.inventory import InventoryItemCreate, InventoryItemUpdate
from app.services.recipes import get_or_create_ingredient


class DuplicateItemError(Exception):
    """The ingredient is already in the inventory (one row per ingredient)."""

    def __init__(self, existing: InventoryItem):
        self.existing_id = existing.id
        super().__init__(f"'{existing.name}' is already in your inventory. Edit that item instead.")


class InvalidItemError(Exception):
    """The combined item doesn't make sense, e.g. a unit with no quantity."""


def _find_by_ingredient(db: Session, ingredient_id: int) -> Optional[InventoryItem]:
    return db.scalar(select(InventoryItem).where(InventoryItem.ingredient_id == ingredient_id))


def list_items(
    db: Session,
    search: Optional[str] = None,
    location: Optional[str] = None,
    expires_within: Optional[int] = None,
    today: Optional[date] = None,
) -> list[InventoryItem]:
    """Soonest expiration first; items with no date go last, then alphabetical."""
    query = (
        select(InventoryItem)
        .join(InventoryItem.ingredient)
        .order_by(
            InventoryItem.expiration_date.is_(None),  # False (has a date) sorts before True
            InventoryItem.expiration_date,
            Ingredient.name,
        )
    )
    if search and search.strip():
        term = " ".join(search.lower().split())
        query = query.where(Ingredient.name.contains(term, autoescape=True))
    if location:
        query = query.where(InventoryItem.location == location)
    if expires_within is not None:
        # Includes items that have already expired: those need attention too.
        cutoff = (today or date.today()) + timedelta(days=expires_within)
        query = query.where(InventoryItem.expiration_date <= cutoff)
    return list(db.scalars(query))


def get_item(db: Session, item_id: int) -> Optional[InventoryItem]:
    return db.get(InventoryItem, item_id)


def create_item(db: Session, data: InventoryItemCreate) -> InventoryItem:
    ingredient = get_or_create_ingredient(db, data.name, data.category)
    existing = _find_by_ingredient(db, ingredient.id)
    if existing is not None:
        error = DuplicateItemError(existing)  # read its name before rollback expires it
        db.rollback()  # don't keep a half-finished new ingredient around
        raise error

    item = InventoryItem(
        ingredient=ingredient,
        **data.model_dump(exclude={"name", "category"}),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, item: InventoryItem, data: InventoryItemUpdate) -> InventoryItem:
    changes = data.model_dump(exclude_unset=True, exclude={"name"})

    # Check the item as it will look after the change, e.g. PATCH {"unit": "cup"}
    # on an item whose quantity is "some" would leave a unit with no amount.
    new_quantity = changes.get("quantity", item.quantity)
    new_unit = changes.get("unit", item.unit)
    if "quantity" in changes and changes["quantity"] is None and "unit" not in changes:
        new_unit = changes["unit"] = None  # "some" has no unit
    if new_unit and new_quantity is None:
        raise InvalidItemError("unit needs a quantity")

    if data.name is not None and data.name != item.name:
        ingredient = get_or_create_ingredient(db, data.name)
        if ingredient.id == item.ingredient_id:
            # "scallion" -> "green onion": same ingredient by key, but the user wants the new name.
            ingredient = get_or_create_ingredient(db, data.name, exact=True)
        existing = _find_by_ingredient(db, ingredient.id)
        if existing is not None and existing.id != item.id:
            error = DuplicateItemError(existing)
            db.rollback()
            raise error
        item.ingredient = ingredient

    for field, value in changes.items():
        setattr(item, field, value)

    item.updated_at = utc_now()
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item: InventoryItem) -> None:
    db.delete(item)  # the shared ingredient row stays; recipes may still use it
    db.commit()


def list_ingredients(db: Session) -> list[Ingredient]:
    """Every known ingredient, for autocomplete. Picking one keeps names matching recipes."""
    return list(db.scalars(select(Ingredient).order_by(Ingredient.name)))
