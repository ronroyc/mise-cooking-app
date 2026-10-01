"""Grocery list logic: adding (and combining) items, filling from a recipe, and
moving bought items into the inventory."""
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GroceryItem, Ingredient, InventoryItem
from app.models.inventory import expiration_status
from app.models.recipe import utc_now
from app.schemas.recipe import RecipeOut
from app.services import matching, units
from app.services.names import match_key
from app.services.recipes import get_or_create_ingredient

# Where a bought item goes, by grocery category. Anything else goes in the pantry.
LOCATION_BY_CATEGORY = {
    "Produce": "fridge", "Dairy & Eggs": "fridge", "Meat & Seafood": "fridge", "Frozen": "freezer",
}


def location_for(category: Optional[str]) -> str:
    return LOCATION_BY_CATEGORY.get(category or "", "pantry")


def list_items(db: Session) -> list[GroceryItem]:
    """Unchecked first, then by store section, then by name."""
    query = (
        select(GroceryItem)
        .join(GroceryItem.ingredient)
        .order_by(GroceryItem.checked, Ingredient.category.is_(None), Ingredient.category, Ingredient.name,
                  GroceryItem.id)
    )
    return list(db.scalars(query))


def to_buy_lines(db: Session) -> list[str]:
    """Unchecked items as short lines, like "Rice (2 cups)" or "Salt"."""
    lines = []
    for item in list_items(db):
        if item.checked:
            continue
        amount = units.format_amount(item.quantity, item.unit)
        name = item.name[:1].upper() + item.name[1:]
        lines.append(f"{name} ({amount})" if amount else name)
    return lines


def get_item(db: Session, item_id: int) -> Optional[GroceryItem]:
    return db.get(GroceryItem, item_id)


def _add_recipe_title(item: GroceryItem, title: Optional[str]) -> None:
    if not title:
        return
    titles = item.for_recipes.split(", ") if item.for_recipes else []
    if title not in titles:
        item.for_recipes = ", ".join(titles + [title])


def _merge(item: GroceryItem, quantity: Optional[float], unit: Optional[str]) -> bool:
    """Add an amount to an existing row. False if the amounts can't be added together."""
    if quantity is None:
        return True  # "some" adds nothing measurable
    if item.quantity is None:
        item.quantity, item.unit = quantity, unit
        return True
    extra = units.convert(quantity, unit, item.unit)
    if extra is None:
        return False
    total, new_unit = units.tidy(item.quantity + extra, item.unit)
    item.quantity, item.unit = round(total, 4), new_unit
    return True


def add_item(
    db: Session, name: str, quantity: Optional[float], unit: Optional[str], recipe_title: Optional[str] = None,
    commit: bool = True,
) -> GroceryItem:
    """Add to the list, combining with an unchecked row for the same ingredient when possible."""
    ingredient = get_or_create_ingredient(db, name)
    candidates = db.scalars(
        select(GroceryItem).where(GroceryItem.ingredient_id == ingredient.id, GroceryItem.checked.is_(False))
    )
    item = next((c for c in candidates if _merge(c, quantity, unit)), None)
    if item is None:
        item = GroceryItem(ingredient=ingredient, quantity=quantity, unit=unit)
        db.add(item)
    _add_recipe_title(item, recipe_title)
    if commit:
        db.commit()
        db.refresh(item)
    return item


def add_from_recipe(db: Session, recipe: RecipeOut) -> tuple[list[GroceryItem], int]:
    """Add what's missing for a (possibly scaled) recipe: the full amount for missing or
    expired ingredients, the difference for short ones. Optional ingredients are skipped.

    Returns the rows added or updated, and how many optional ingredients were skipped.
    """
    match = matching.match_recipe(db, recipe)
    added, skipped_optional = [], 0
    for needed, found in zip(recipe.ingredients, match.ingredients):
        if found.status in matching.ON_HAND:
            continue
        if needed.optional:
            skipped_optional += 1
            continue
        quantity = needed.quantity
        if found.status == "short":
            item = db.get(InventoryItem, found.inventory_item_id)
            have = units.convert(item.quantity, item.unit, needed.unit)
            quantity = round(needed.quantity - have, 4)
        added.append(add_item(db, needed.name, quantity, needed.unit, recipe.title, commit=False))
    db.commit()
    for item in added:
        db.refresh(item)
    return added, skipped_optional


class InvalidItemError(Exception):
    """The combined item doesn't make sense, e.g. a unit with no quantity."""


def update_item(db: Session, item: GroceryItem, changes: dict) -> GroceryItem:
    if "quantity" in changes and changes["quantity"] is None and "unit" not in changes:
        changes["unit"] = None  # "some" has no unit
    if changes.get("unit", item.unit) and changes.get("quantity", item.quantity) is None:
        raise InvalidItemError("unit needs a quantity")
    for field, value in changes.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item: GroceryItem) -> None:
    db.delete(item)
    db.commit()


def clear_checked(db: Session) -> int:
    items = list(db.scalars(select(GroceryItem).where(GroceryItem.checked.is_(True))))
    for item in items:
        db.delete(item)
    db.commit()
    return len(items)


def stock_checked(db: Session, today: Optional[date] = None) -> list[str]:
    """Move every checked item into the inventory and off the list.

    Returns one plain sentence per item saying what happened.
    """
    today = today or date.today()
    inventory = matching.inventory_by_key(db)
    messages = []
    for grocery in db.scalars(select(GroceryItem).where(GroceryItem.checked.is_(True)).order_by(GroceryItem.id)):
        bought = units.describe_amount(grocery.quantity, grocery.unit, grocery.name)
        kept = inventory.get(match_key(grocery.name))

        if kept is None:
            kept = InventoryItem(
                ingredient=grocery.ingredient, quantity=grocery.quantity, unit=grocery.unit,
                location=location_for(grocery.category),
            )
            db.add(kept)
            inventory[match_key(grocery.name)] = kept
            messages.append(f"Added {grocery.name} ({bought}) to your {kept.location}.")
        elif expiration_status(kept.expiration_date, today) == "expired":
            # The old one is past its date: the new one replaces it.
            kept.quantity, kept.unit, kept.expiration_date = grocery.quantity, grocery.unit, None
            messages.append(f"Replaced your expired {kept.name} with {bought}.")
        elif kept.quantity is None or grocery.quantity is None:
            messages.append(f"You already had {kept.name}; it's still listed as {units.describe_amount(kept.quantity, kept.unit, kept.name)}.")
        else:
            extra = units.convert(grocery.quantity, grocery.unit, kept.unit)
            if extra is None:
                messages.append(
                    f"Couldn't add {bought} to your {kept.name} ({units.describe_amount(kept.quantity, kept.unit, kept.name)}): "
                    "the units don't convert. Update the amount on the Inventory page."
                )
            else:
                kept.quantity = round(kept.quantity + extra, 4)
                messages.append(f"Added {bought} to your {kept.name}; you now have "
                                f"{units.describe_amount(kept.quantity, kept.unit, kept.name)}.")
        kept.updated_at = utc_now()
        db.delete(grocery)
    db.commit()
    return messages
