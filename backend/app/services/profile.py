"""The profile: what Mise knows about how you cook, from what you actually do.

Nothing here comes from a questionnaire. It's built from the cooking history,
ratings, pins, and saved recipes, and every section has a minimum amount of data
before it says anything. With too little data, the page says what's missing
("cook 2 more meals") instead of guessing.

Your flavor profile: the average flavor (services/flavors.py) of the meals you've
cooked and the recipes you've pinned. A meal counts once per time you cooked it;
a rated meal counts rating / 3 (a 5 counts 1.67, a 1 counts 0.33), so recipes you
liked pull the shape toward them. A pin counts 1.
"""
from collections import Counter
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CookingLog, Recipe
from app.services import taste
from app.services.flavors import FLAVORS, LABELS, level, recipe_flavor
from app.services.matching import STAPLES
from app.services.names import match_key

MIN_FLAVOR_SOURCES = 3   # meals cooked + recipes pinned, before showing a flavor profile
MIN_MEALS_FOR_HABITS = 3  # before "you cook with..." uses meals instead of saved recipes
MIN_MEALS_FOR_OBSERVATIONS = 5
MIN_RATED_FOR_RATING_OBSERVATIONS = 6
QUICK_MINUTES = 30
MAX_OBSERVATIONS = 5

# How each flavor reads in a sentence: "You like spicy food."
FLAVOR_WORDS = {
    "heat": "spicy", "sweet": "sweet", "sour": "sour", "salty": "salty",
    "umami": "savory, umami-rich", "garlicky": "garlicky", "herby": "herby", "creamy": "creamy",
}
TOP_INGREDIENTS = 8


def _plural(count: int, word: str, plural: Optional[str] = None) -> str:
    return f"{count} {word if count == 1 else (plural or word + 's')}"


def _weight(log: CookingLog) -> float:
    return log.rating / 3 if log.rating else 1.0


def _flavor_profile(logs, pinned):
    """(values, basis sentence) or (None, what's missing)."""
    sources = [(recipe_flavor(log.recipe.ingredients)["values"], _weight(log)) for log in logs]
    sources += [(recipe_flavor(recipe.ingredients)["values"], 1.0) for recipe in pinned]
    parts = []
    if logs:
        parts.append(_plural(len(logs), "meal") + " you cooked")
    if pinned:
        parts.append(_plural(len(pinned), "recipe") + " you pinned")
    if len(sources) < MIN_FLAVOR_SOURCES:
        needed = MIN_FLAVOR_SOURCES - len(sources)
        return None, (f"Cook or pin {_plural(needed, 'more recipe')} to see your flavor profile. "
                      f"It needs at least {MIN_FLAVOR_SOURCES}, and so far there {'is' if len(sources) == 1 else 'are'} "
                      f"{len(sources)}.")
    total = sum(weight for _, weight in sources)
    values = {f: round(sum(v[f] * w for v, w in sources) / total, 3) for f in FLAVORS}
    basis = f"Based on {' and '.join(parts)}."
    if any(log.rating for log in logs):
        basis += " Meals you rated higher count more."
    return values, basis


def _top_ingredients(recipes_used: list) -> list:
    """[(name, count)] of the most-used ingredients, leaving out salt, pepper, and water."""
    counts, spelling = Counter(), {}
    for recipe in recipes_used:
        for item in recipe.ingredients:
            key = match_key(item.name)
            if key in STAPLES:
                continue
            counts[key] += 1
            spelling.setdefault(key, item.name)
    return [{"name": spelling[key], "count": count} for key, count in counts.most_common(TOP_INGREDIENTS)]


def _average(values) -> Optional[float]:
    values = list(values)
    return round(sum(values) / len(values), 1) if values else None


def _observations(logs, flavors_by_log) -> list:
    """Things Mise can say with numbers behind them. Each one needs enough meals."""
    found = []
    if len(logs) < MIN_MEALS_FOR_OBSERVATIONS:
        return found

    # A go-to recipe: cooked at least 3 times.
    times = Counter(log.recipe_title for log in logs)
    title, count = times.most_common(1)[0]
    if count >= 3:
        found.append({"title": f"Your go-to is {title}.", "detail": f"You've cooked it {count} times."})

    # A cuisine that's at least 40% of meals.
    cuisines = Counter(log.recipe.cuisine for log in logs if log.recipe.cuisine)
    if cuisines:
        cuisine, count = cuisines.most_common(1)[0]
        if count / len(logs) >= 0.4:
            found.append({"title": f"You cook a lot of {cuisine} food.",
                          "detail": f"{count} of your {len(logs)} meals were {cuisine}."})

    # The flavor in the most meals, if it's in at least 70% of them.
    shares = [(sum(values[f] >= 0.5 for values in flavors_by_log), f) for f in FLAVORS]
    strong, flavor = max(shares)
    if strong / len(logs) >= 0.7:
        found.append({"title": f"You cook {FLAVOR_WORDS[flavor]} food most of the time.",
                      "detail": f"{strong} of your {len(logs)} meals scored high on {LABELS[flavor].lower()}."})

    rated = [(log, values) for log, values in zip(logs, flavors_by_log) if log.rating]
    if len(rated) < MIN_RATED_FOR_RATING_OBSERVATIONS:
        return found

    # Quick recipes vs longer ones, when both have at least 2 rated meals and differ by half a star.
    quick = [log.rating for log, _ in rated if log.recipe.total_time <= QUICK_MINUTES]
    slow = [log.rating for log, _ in rated if log.recipe.total_time > QUICK_MINUTES]
    if len(quick) >= 2 and len(slow) >= 2:
        q, s = sum(quick) / len(quick), sum(slow) / len(slow)
        if abs(q - s) >= 0.5:
            better, worse = ("Quick recipes", "longer ones") if q > s else ("Longer recipes", "quick ones")
            found.append({"title": f"{better} rate higher for you.",
                          "detail": f"{max(q, s):.1f} on average for recipes {'under' if q > s else 'over'} "
                                    f"{QUICK_MINUTES} minutes, {min(q, s):.1f} for {worse}."})

    # Flavors you rate higher or lower than the rest: the two clearest likes and the clearest dislike.
    gaps = []
    for flavor in FLAVORS:
        with_it = [log.rating for log, values in rated if values[flavor] >= 0.5]
        without = [log.rating for log, values in rated if values[flavor] < 0.5]
        if len(with_it) >= 2 and len(without) >= 2:
            a, b = sum(with_it) / len(with_it), sum(without) / len(without)
            if abs(a - b) >= 0.5:
                gaps.append((a - b, flavor, a, b))
    likes = sorted((g for g in gaps if g[0] > 0), reverse=True)[:2]
    dislikes = sorted(g for g in gaps if g[0] < 0)[:1]
    for _, flavor, a, b in likes:
        found.append({"title": f"You like {FLAVOR_WORDS[flavor]} food.",
                      "detail": f"You rate {LABELS[flavor].lower()} meals {a:.1f} on average, other meals {b:.1f}."})
    for _, flavor, a, b in dislikes:
        found.append({"title": f"{FLAVOR_WORDS[flavor].capitalize()} food isn't your favorite.",
                      "detail": f"You rate {LABELS[flavor].lower()} meals {a:.1f} on average, other meals {b:.1f}."})
    return found[:MAX_OBSERVATIONS]


def build_profile(db: Session, today: Optional[date] = None) -> dict:
    all_logs = list(db.scalars(select(CookingLog).order_by(CookingLog.cooked_on, CookingLog.id)))
    logs = [log for log in all_logs if log.recipe is not None]  # deleted recipes have no ingredients left
    recipes = list(db.scalars(select(Recipe).order_by(Recipe.id)))
    pinned = [r for r in recipes if r.pinned_at is not None]
    ratings = [log.rating for log in all_logs if log.rating]

    values, basis = _flavor_profile(logs, pinned)
    flavor = None
    if values is not None:
        flavor = {
            "values": [{"flavor": f, "label": LABELS[f], "value": values[f], "level": level(values[f])} for f in FLAVORS],
            "basis": basis,
        }

    cuisines = Counter(log.recipe.cuisine for log in logs if log.recipe.cuisine)
    top_cuisine = cuisines.most_common(1)[0] if cuisines and len(logs) >= 2 else None

    your_taste = taste.learn(db)
    from_meals = len(logs) >= MIN_MEALS_FOR_HABITS
    flavors_by_log = [recipe_flavor(log.recipe.ingredients)["values"] for log in logs]
    return {
        "stats": {
            "meals_cooked": len(all_logs),
            "different_recipes": len({log.recipe_title for log in all_logs}),
            "recipes_saved": len(recipes),
            "recipes_pinned": len(pinned),
            "meals_rated": len(ratings),
            "average_rating": _average(ratings),
            "average_minutes": round(sum(log.recipe.total_time for log in logs) / len(logs)) if logs else None,
            "top_cuisine": {"name": top_cuisine[0], "meals": top_cuisine[1]} if top_cuisine else None,
        },
        "flavor": flavor,
        "flavor_missing": None if flavor else basis,
        "ingredients": {
            "source": "meals" if from_meals else "recipes",
            "items": _top_ingredients([log.recipe for log in logs] if from_meals else recipes),
        },
        # What recommendations follow (services/taste.py), or how many ratings until they do.
        "taste": {"likes": [LABELS[f] for f in your_taste.likes()], "liked_meals": your_taste.liked_meals}
                 if your_taste else None,
        "taste_needed": taste.needed_ratings(db),
        "observations": _observations(logs, flavors_by_log),
        "observations_needed": max(MIN_MEALS_FOR_OBSERVATIONS - len(logs), 0),
    }
