"""Recommendations: rank recipes by what's already in the kitchen.

Deterministic on purpose: the same inventory always gives the same ranking, and every
point of the score can be explained in plain words.

    score (0-100) = coverage points (up to 70) + use-soon points (up to 20) + taste points (up to 10)

Coverage: the share of required ingredients on hand. "have" and "staple" count fully,
"short" counts half, "expired" and "missing" count zero. Optional ingredients don't count.

Use soon: 10 points for each ingredient the recipe uses that expires within 3 days
(up to 2 of them), so food gets cooked before it goes off.

Taste: how well the recipe's flavor fits the meals you rate 4 or 5 (services/taste.py).
Zero for everyone until there are 3 such meals. It's the smallest part on purpose:
it reorders recipes you can make, it doesn't push ones you can't.
"""
from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inventory import EXPIRING_SOON_DAYS, InventoryItem
from app.schemas.recipe import IngredientMatch, RecipeMatchOut, RecipeOut
from app.schemas.recommendation import Recommendation, RecommendationList
from app.services import matching, taste
from app.services import recipes as recipe_service
from app.services.flavors import recipe_flavor

COVERAGE_POINTS = 70
USE_SOON_POINTS_EACH = 10
USE_SOON_MAX_ITEMS = 2
CREDIT = {"have": 1.0, "staple": 1.0, "short": 0.5, "expired": 0.0, "missing": 0.0}

# How many names to list in a reason before "and 2 more".
MAX_NAMES = 3


def _names(items: list) -> str:
    """['ginger', 'soy sauce'] -> 'ginger and soy sauce'; long lists end with 'and N more'."""
    names = [i.name for i in items]
    if len(names) > MAX_NAMES:
        shown = names[:MAX_NAMES]
        return f"{', '.join(shown)}, and {len(names) - MAX_NAMES} more"
    if len(names) <= 2:
        return " and ".join(names)
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def _when(days: int) -> str:
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    return f"in {days} days"


def expiring_soon(match: RecipeMatchOut) -> list[IngredientMatch]:
    """Ingredients this recipe would use up that expire within 3 days (not already expired)."""
    return [
        m for m in match.ingredients
        if m.status in ("have", "short")
        and m.expires_in_days is not None
        and 0 <= m.expires_in_days <= EXPIRING_SOON_DAYS
    ]


def score_recipe(recipe: RecipeOut, match: RecipeMatchOut, your_taste: Optional[taste.Taste] = None) -> Recommendation:
    required = [m for m in match.ingredients if not m.optional]
    coverage = sum(CREDIT[m.status] for m in required) / len(required) if required else 1.0
    coverage_points = round(COVERAGE_POINTS * coverage)
    soon = sorted(expiring_soon(match), key=lambda m: m.expires_in_days)
    use_soon_points = USE_SOON_POINTS_EACH * min(len(soon), USE_SOON_MAX_ITEMS)
    taste_points, shared_flavors = taste.fit(your_taste, recipe_flavor(recipe.ingredients)["values"])

    missing = [m for m in required if m.status == "missing"]
    short = [m for m in required if m.status == "short"]
    expired = [m for m in required if m.status == "expired"]

    reasons = []
    if match.ready:
        reasons.append("You have everything you need.")
    else:
        noun = "ingredient" if match.required_count == 1 else "ingredients"
        reasons.append(f"You have {match.have_count} of {match.required_count} {noun}.")
    for m in soon[:USE_SOON_MAX_ITEMS]:
        reasons.append(f"Uses your {m.inventory_name}, expiring {_when(m.expires_in_days)}.")  # no verb, so plurals read right
    if taste_points >= 3 and shared_flavors:
        reasons.append(f"Fits your taste: {taste.describe(shared_flavors[:2])}, like the meals you rate 4 or 5.")
    if short:
        reasons.append(f"Not enough {_names(short)}.")
    if expired:
        reasons.append(f"Past its date: {_names(expired)}.")
    if missing:
        reasons.append(f"Missing {_names(missing)}.")

    return Recommendation(
        recipe=recipe,
        score=coverage_points + use_soon_points + taste_points,
        coverage_points=coverage_points,
        use_soon_points=use_soon_points,
        taste_points=taste_points,
        ready=match.ready,
        color=match.color,
        have_count=match.have_count,
        swap_count=match.swap_count,
        required_count=match.required_count,
        missing=[m.name for m in missing],
        short=[m.name for m in short],
        expired=[m.name for m in expired],
        use_soon=[m.inventory_name for m in soon],
        reasons=reasons,
    )


def recommend(
    db: Session,
    search: Optional[str] = None,
    cuisine: Optional[str] = None,
    max_total_time: Optional[int] = None,
    limit: Optional[int] = None,
    today: Optional[date] = None,
    pinned_only: bool = False,
) -> RecommendationList:
    """Every recipe that passes the filters, best match first.

    Ties go to fewer missing ingredients, then the quicker recipe, then the title.
    """
    today = today or date.today()
    inventory = matching.inventory_by_key(db)  # load once for all recipes
    your_taste = taste.learn(db)                # and learn your taste once
    results = []
    for row in recipe_service.list_recipes(db, search, cuisine, max_total_time, pinned_only):
        recipe = RecipeOut.model_validate(row)
        match = matching.match_recipe(db, recipe, today=today, inventory=inventory)
        results.append(score_recipe(recipe, match, your_taste))
    results.sort(key=lambda r: (-r.score, len(r.missing), r.recipe.total_time, r.recipe.title.lower()))
    return RecommendationList(
        inventory_count=db.scalar(select(func.count()).select_from(InventoryItem)),
        recommendations=results[:limit] if limit else results,
    )
