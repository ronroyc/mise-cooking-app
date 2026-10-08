"""Taste: what you like, learned from your ratings, and how well a recipe fits it.

1. Your lean: the average flavor (services/flavors.py) of the meals you rated 4 or 5,
   minus the average flavor of all your saved recipes. Subtracting matters: nearly
   every recipe is a bit salty, so "salty" only counts as your taste when the meals
   you liked are saltier than your recipes in general.
2. A recipe's lean: its flavor minus that same average.
3. Fit: the cosine similarity of the two leans, from -1 (opposite) to 1 (same
   direction). Only the positive part earns points: up to 10 in the recommendation
   score, so taste reorders recipes but never beats what's actually in the kitchen.

Nothing is guessed: with fewer than 3 meals rated 4 or 5, there's no lean, and every
recipe gets 0 taste points.
"""
import math
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CookingLog, Recipe
from app.services import recipes as recipe_service
from app.services.flavors import FLAVORS, LABELS, recipe_flavor

MIN_LIKED_MEALS = 3
LIKED_RATING = 4
TASTE_POINTS = 10
NOTICEABLE = 0.05  # a lean smaller than this, in one flavor, doesn't count as a preference


@dataclass
class Taste:
    lean: dict       # flavor -> how much more (or less) the liked meals have than your recipes overall
    baseline: dict   # flavor -> average over all saved recipes
    liked_meals: int

    def likes(self) -> list:
        """Flavors you clearly lean toward, strongest first: ["garlicky", "salty"]."""
        return [f for f in sorted(FLAVORS, key=lambda f: -self.lean[f]) if self.lean[f] >= NOTICEABLE]


def _average(vectors: list) -> dict:
    return {f: sum(v[f] for v in vectors) / len(vectors) for f in FLAVORS}


def _length(vector: dict) -> float:
    return math.sqrt(sum(v * v for v in vector.values()))


def learn(db: Session) -> Optional[Taste]:
    """Your taste from your ratings, or None if there aren't enough liked meals yet."""
    liked = [
        log for log in db.scalars(select(CookingLog).where(CookingLog.rating >= LIKED_RATING))
        if log.recipe is not None
    ]
    if len(liked) < MIN_LIKED_MEALS:
        return None
    recipes = list(db.scalars(select(Recipe).options(*recipe_service.WITH_DETAILS)))
    baseline = _average([recipe_flavor(r.ingredients)["values"] for r in recipes])
    liked_average = _average([recipe_flavor(log.recipe.ingredients)["values"] for log in liked])
    lean = {f: liked_average[f] - baseline[f] for f in FLAVORS}
    if _length(lean) < NOTICEABLE:
        return None  # you like everything about equally: no direction to follow
    return Taste(lean=lean, baseline=baseline, liked_meals=len(liked))


def needed_ratings(db: Session) -> int:
    """How many more meals rated 4 or 5 before taste counts."""
    liked = sum(1 for log in db.scalars(select(CookingLog).where(CookingLog.rating >= LIKED_RATING))
                if log.recipe is not None)
    return max(MIN_LIKED_MEALS - liked, 0)


def fit(taste: Optional[Taste], flavor_values: dict) -> tuple:
    """(points 0-10, flavors this recipe shares with your taste) for one recipe's flavor."""
    if taste is None:
        return 0, []
    recipe_lean = {f: flavor_values[f] - taste.baseline[f] for f in FLAVORS}
    length = _length(recipe_lean) * _length(taste.lean)
    if length == 0:
        return 0, []
    similarity = sum(recipe_lean[f] * taste.lean[f] for f in FLAVORS) / length
    shared = [f for f in taste.likes() if recipe_lean[f] >= NOTICEABLE]
    return round(TASTE_POINTS * max(similarity, 0)), shared


def describe(flavors: list) -> str:
    """["garlicky", "salty"] -> "garlicky and salty"."""
    words = [LABELS[f].lower() for f in flavors]
    return " and ".join(words) if len(words) <= 2 else f"{', '.join(words[:-1])}, and {words[-1]}"
