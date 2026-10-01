"""Ingredient matching: which of a recipe's ingredients are already in the kitchen?

Each recipe ingredient gets one status:

    have     in the inventory, and enough of it (or the amount can't be compared)
    short    in the inventory, but less than the recipe needs
    expired  in the inventory, but past its date
    staple   not in the inventory, but it's salt, pepper, or water: assumed to be there
    missing  not in the inventory

"Can't be compared" covers inventory amounts of "some", "to taste" in the recipe, and
units of different kinds (2 lb of flour vs 1 cup). Those count as "have", since the
ingredient is there and guessing a conversion would be worse than trusting the cook.
"""
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InventoryItem
from app.models.inventory import expiration_status
from app.schemas.recipe import IngredientMatch, RecipeIngredientOut, RecipeMatchOut, RecipeOut, SwapOption
from app.services import units
from app.services.substitutions import find_swaps
from app.services.names import match_key

# A little slack so 2.9999 cups (rounding after conversion) counts as 3.
TOLERANCE = 0.01

# Match keys of things nearly every kitchen has and nobody tracks. Without this, almost
# every recipe would be "missing salt". If the inventory does list one, that item is used.
STAPLES = {"salt", "black pepper", "water"}

# Statuses that mean "you can cook with what you have".
ON_HAND = ("have", "staple")


def inventory_by_key(db: Session) -> dict:
    """match key -> inventory item. Loaded once, then reused for every ingredient."""
    found = {}
    for item in db.scalars(select(InventoryItem).order_by(InventoryItem.id)):
        found.setdefault(match_key(item.name), item)
    return found


def match_ingredient(
    needed: RecipeIngredientOut, item: Optional[InventoryItem], today: date
) -> IngredientMatch:
    result = IngredientMatch(
        name=needed.name,
        display_name=needed.display_name,
        amount_text=needed.amount_text,
        optional=needed.optional,
        status="missing",
        inventory_item_id=None,
        inventory_name=None,
        inventory_amount_text=None,
        expires_in_days=None,
        note=None,
    )
    if item is None:
        if match_key(needed.name) in STAPLES:
            result.status = "staple"
        return result

    result.inventory_item_id = item.id
    result.inventory_name = item.name
    result.inventory_amount_text = units.describe_amount(item.quantity, item.unit, item.name)
    if item.expiration_date is not None:
        result.expires_in_days = (item.expiration_date - today).days

    if expiration_status(item.expiration_date, today) == "expired":
        result.status = "expired"
        result.note = f"Your {item.name} is past its date."
        return result

    result.status = "have"
    if needed.quantity is None or item.quantity is None:
        return result
    have = units.convert(item.quantity, item.unit, needed.unit)
    needs = units.describe_amount(needed.quantity, needed.unit, needed.name)
    if have is None:
        result.note = f"You have {result.inventory_amount_text}; this needs {needs}. Check it's enough."
        return result
    if have < needed.quantity * (1 - TOLERANCE):
        result.status = "short"
        result.note = f"You have {result.inventory_amount_text}; this needs {needs}."
    return result


def match_color(have_count: int, required_count: int) -> str:
    """The corner tab on recipe cards.

    green   every required ingredient on hand, in enough quantity
    yellow  at least half of them
    red     less than half

    "Short" and "expired" ingredients don't count as on hand.
    """
    if have_count >= required_count:
        return "green"
    if have_count * 2 >= required_count:
        return "yellow"
    return "red"


def match_recipe(
    db: Session, recipe: RecipeOut, today: Optional[date] = None, inventory: Optional[dict] = None
) -> RecipeMatchOut:
    """Compare a (possibly scaled) recipe with the inventory.

    Pass `inventory` from inventory_by_key() when matching many recipes, to load it once.
    """
    today = today or date.today()
    inventory = inventory if inventory is not None else inventory_by_key(db)
    matches = [match_ingredient(i, inventory.get(match_key(i.name)), today) for i in recipe.ingredients]
    for m in matches:
        if m.status not in ON_HAND:
            m.swaps = [SwapOption(**s) for s in find_swaps(m.name, inventory, today, frozenset(STAPLES))]
    required = [m for m in matches if not m.optional]
    have_count = sum(m.status in ON_HAND for m in required)
    return RecipeMatchOut(
        recipe_id=recipe.id,
        servings=recipe.servings,
        required_count=len(required),
        have_count=have_count,
        ready=all(m.status in ON_HAND for m in required),
        color=match_color(have_count, len(required)),
        swap_count=sum(m.status not in ON_HAND and any(s.have for s in m.swaps) for m in required),
        ingredients=matches,
    )
