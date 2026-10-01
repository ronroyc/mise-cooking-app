"""Cooking history: logging a cooked recipe, taking what it used out of the inventory,
and saving leftovers to the fridge."""
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CookingLog, InventoryItem, Recipe
from app.models.recipe import utc_now
from app.schemas.recipe import RecipeOut
from app.services import matching, units
from app.services.names import match_key
from app.services.recipes import get_or_create_ingredient

# Less than this fraction of the amount left counts as used up (rounding after conversion).
USED_UP = 0.01


def use_ingredients(db: Session, recipe: RecipeOut) -> list[str]:
    """Subtract a (possibly scaled) recipe's amounts from the inventory.

    Only measured amounts in units that convert are subtracted. Items that run out are
    removed. Optional ingredients, "to taste", and "some" are left alone, since there's
    no way to know how much was used. Returns one plain sentence per inventory change.
    """
    inventory = matching.inventory_by_key(db)
    messages = []
    for needed in recipe.ingredients:
        item: Optional[InventoryItem] = inventory.get(match_key(needed.name))
        if item is None or needed.optional or needed.quantity is None or item.quantity is None:
            continue
        used = units.convert(needed.quantity, needed.unit, item.unit)
        if used is None:
            messages.append(f"Left your {item.name} as is: {needed.amount_text} doesn't convert to {item.unit}.")
            continue
        left = item.quantity - used
        if left <= item.quantity * USED_UP:
            db.delete(item)
            inventory.pop(match_key(needed.name))
            messages.append(f"Used up your {item.name}, so it's off the inventory.")
        else:
            item.quantity = round(left, 4)
            item.updated_at = utc_now()
            # Shown in a clean unit (2 tbsp, not 1/8 cup); the stored unit doesn't change.
            used_text = units.describe_amount(*units.tidy(used, item.unit), item.name)  # "2 cups" or "3 eggs"
            if (item.unit or "each") != "each":
                used_text += f" {item.name}"  # "2 cups rice"
            left_text = units.describe_amount(*units.tidy(item.quantity, item.unit), item.name)
            messages.append(f"Used {used_text}; {left_text} left.")
    return messages


# Cooked food keeps 3 to 4 days in the fridge (USDA guidance). From the day it was cooked.
LEFTOVER_DAYS = 4


def save_leftovers(db: Session, title: str, servings: int, cooked_on: date, today: date) -> str:
    """Put leftovers in the fridge as an inventory item: "leftover chicken fried rice", 2 servings.

    Leftovers of the same recipe already in the fridge are added to, keeping the
    earlier date (the older portion goes bad first).
    """
    good_until = cooked_on + timedelta(days=LEFTOVER_DAYS)
    amount = units.format_amount(servings, "serving")
    if good_until < today:
        return f"Didn't save leftovers: food cooked on {cooked_on:%b %-d} is past the {LEFTOVER_DAYS} days it keeps."
    ingredient = get_or_create_ingredient(db, f"leftover {title.lower()}"[:100], category="Leftovers", exact=True)
    item = db.scalar(select(InventoryItem).where(InventoryItem.ingredient_id == ingredient.id))
    if item is not None and item.unit == "serving" and item.quantity is not None and \
            (item.expiration_date is None or item.expiration_date >= today):
        item.quantity += servings
        item.expiration_date = min(d for d in (item.expiration_date, good_until) if d is not None)
        item.updated_at = utc_now()
        total = units.format_amount(item.quantity, "serving")
        return f"Added {amount} to your leftover {title}; {total} in the fridge, good until {item.expiration_date:%b %-d}."
    if item is not None:  # an old, expired, or unmeasured entry: replace it
        db.delete(item)
        db.flush()
    db.add(InventoryItem(ingredient=ingredient, quantity=servings, unit="serving", location="fridge",
                         expiration_date=good_until))
    return f"Saved {amount} of {title} as leftovers in the fridge, good until {good_until:%b %-d}."


def log_cooked(
    db: Session, recipe: Recipe, scaled: RecipeOut, cooked_on: date, rating: Optional[int],
    notes: Optional[str], update_inventory: bool, leftover_servings: Optional[int] = None,
    today: Optional[date] = None,
) -> tuple[CookingLog, list[str]]:
    log = CookingLog(
        recipe=recipe, recipe_title=recipe.title, cooked_on=cooked_on, servings=scaled.servings,
        rating=rating, notes=notes,
    )
    db.add(log)
    messages = use_ingredients(db, scaled) if update_inventory else []
    if leftover_servings:
        messages.append(save_leftovers(db, recipe.title, leftover_servings, cooked_on, today or date.today()))
    db.commit()
    db.refresh(log)
    return log, messages


def list_logs(db: Session, recipe_id: Optional[int] = None) -> list[CookingLog]:
    query = select(CookingLog).order_by(CookingLog.cooked_on.desc(), CookingLog.id.desc())
    if recipe_id is not None:
        query = query.where(CookingLog.recipe_id == recipe_id)
    return list(db.scalars(query))


def get_log(db: Session, log_id: int) -> Optional[CookingLog]:
    return db.get(CookingLog, log_id)


def update_log(db: Session, log: CookingLog, changes: dict) -> CookingLog:
    for field, value in changes.items():
        setattr(log, field, value)
    db.commit()
    db.refresh(log)
    return log


def delete_log(db: Session, log: CookingLog) -> None:
    db.delete(log)
    db.commit()
