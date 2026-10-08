"""Recipes from TheMealDB (https://www.themealdb.com), a free recipe catalog, with plain code.

TheMealDB lists each recipe's ingredients as pairs ("1/2 cup" + "brown sugar"), so the
amount and the name arrive already apart. What it doesn't give is cooking times or
servings. Cook time is added up from the steps ("bake 35 minutes", "simmer for 20 minutes"),
prep time is a rough 2 minutes per ingredient, and both are marked "estimated". A recipe
with no times in its steps is marked "unknown" and left out of time filters. Servings are a guess of 4 and marked as one.

The command that fetches the catalog and saves it is app/database/mealdb.py.
"""
import json
import re
from typing import Callable, Optional

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Recipe
from app.schemas.recipe import RecipeCreate
from app.services import photos
from app.services import recipes as recipe_service
from app.services.recipe_import import (
    NUMBER, ImportFailed, _clean_fractions, _number, clean_text, fetch, merge_ingredients, parse_amount,
    parse_ingredient_line,
)

API = "https://www.themealdb.com/api/json/v1/1"
SOURCE_PREFIX = "https://www.themealdb.com/meal/"  # + the meal's id: each recipe links back
FIRST_CHARACTERS = "abcdefghijklmnopqrstuvwxyz0123456789"  # the API lists meals by first character
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
GUESSED_SERVINGS = 4  # the amounts are mostly family-sized ("500g beef", "1 lb pasta")
PREP_MINUTES_PER_INGREDIENT = 2  # washing, measuring, chopping: rough, and labeled "about"
MAX_PREP_MINUTES = 30

# TheMealDB mixes adjectives and country names. The app's cuisines are adjectives.
CUISINES = {
    "Argentina": "Argentinian", "France": "French", "India": "Indian", "Netherlands": "Dutch",
    "Norway": "Norwegian", "Slovakia": "Slovak", "United States": "American", "Venezuela": "Venezuelan",
    "Unknown": None,
}

# Amounts that mean "it's for the top": these don't stop a recipe from being READY.
GARNISH = re.compile(r"^(?:to serve|to garnish|for garnish|garnish|topping|to decorate|optional)\b", re.IGNORECASE)
# "Juice of 1" (lemon), "Zest and juice of 2", "Juice/zest of one".
JUICE_OR_ZEST = re.compile(
    r"^(?:the\s+)?(?:grated\s+)?((?:juice|zest)(?:\s*(?:and|/)\s*(?:juice|zest))?)\s+of\s+(\S+)", re.IGNORECASE
)
NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "half": 0.5, "two": 2, "three": 3, "four": 4}


# ---------- Ingredients ----------

def _juice_or_zest(measure: str):
    match = JUICE_OR_ZEST.match(measure)
    if not match:
        return None
    word = match.group(2).lower()
    try:
        quantity = NUMBER_WORDS[word] if word in NUMBER_WORDS else _number(_clean_fractions(word))
    except ValueError:
        return None
    if not 0 < quantity <= 100:
        return None
    return quantity, match.group(1).lower(), measure[match.end():].strip()


def parse_pair(measure: str, name: str) -> Optional[dict]:
    """One ingredient from TheMealDB's amount and name:
    ('2 cloves minced', 'garlic') -> garlic, 2 cloves, "minced"
    ('Juice of 1', 'lemon')       -> lemon, 1, "juice"
    ('To serve', 'parsley')       -> parsley, optional, no amount
    """
    item = parse_ingredient_line(name)  # the name can carry notes too: "minced garlic"
    if not item["name"]:
        return None
    measure = clean_text(measure)
    juice = _juice_or_zest(measure)
    if juice:
        quantity, unit, rest = juice[0], None, f"{juice[1]} {juice[2]}".strip()
    else:
        quantity, unit, rest = parse_amount(measure)
    rest = rest.strip(" ()").lower()
    notes = [note for note in (rest, item["preparation_note"]) if note]
    return {
        "name": item["name"],
        "quantity": quantity,
        "unit": unit if quantity else None,
        "preparation_note": ", ".join(dict.fromkeys(notes))[:200] or None,
        "optional": item["optional"] or bool(GARNISH.match(rest)),
    }


def parse_ingredients(meal: dict) -> tuple:
    """(ingredients, warnings) from strIngredient1..20 and strMeasure1..20."""
    items = []
    for n in range(1, 21):
        name = clean_text(meal.get(f"strIngredient{n}"))
        if name:
            item = parse_pair(meal.get(f"strMeasure{n}") or "", name)
            if item:
                items.append(item)
    return merge_ingredients(items)


# ---------- Steps and times ----------

STEP_LABEL = re.compile(r"^(?:step\s*)?\d+[.):]?$", re.IGNORECASE)          # a line that's only "STEP 1"
STEP_NUMBER = re.compile(r"^(?:step\s*)?\d+\s*[.):]\s*", re.IGNORECASE)      # "1. Heat the oil" -> "Heat the oil"
DURATION = re.compile(
    rf"\b(half an|an|a|{NUMBER})\s*(?:(?:-|–|to|or)\s*({NUMBER})\s*)?(hours?|hrs?|minutes?|mins?)\b",
    re.IGNORECASE,
)


def parse_steps(text: Optional[str]) -> list:
    steps = []
    for line in re.split(r"\r?\n", text or ""):
        line = clean_text(line.replace("▢", " ").replace("​", ""))
        if not line or STEP_LABEL.match(line):
            continue
        line = STEP_NUMBER.sub("", line)
        if line:
            steps.append(line)
    return steps


def estimate_minutes(steps: list) -> int:
    """Every time written in the steps, added up: 'bake 35 minutes' + 'rest 1-2 hours' -> 155.
    A range counts its top. Waiting time (chilling, rising) counts too: it's part of the total."""
    total = 0.0
    for step in steps:
        for amount, high, unit in DURATION.findall(_clean_fractions(step)):
            word = amount.lower()
            value = _number(high) if high else (0.5 if word == "half an" else NUMBER_WORDS.get(word) or _number(amount))
            total += value * 60 if unit.lower().startswith("h") else value
    return min(round(total), 1440)


# ---------- The whole recipe ----------

# "Achiote Oil Recipe", "Ají de Aguacate Recipe (Colombian Spicy Avocado Sauce)": every one is a recipe.
RECIPE_WORD = re.compile(r"\s+recipe\b(?=\s*(?:\(|$))", re.IGNORECASE)


def clean_title(title) -> str:
    return RECIPE_WORD.sub("", clean_text(title))[:200]


def to_recipe(meal: dict) -> dict:
    """The fields of a RecipeCreate, plus time_status, servings_estimated, photo_url, warnings."""
    ingredients, warnings = parse_ingredients(meal)
    steps = parse_steps(meal.get("strInstructions"))
    minutes = estimate_minutes(steps)
    required = sum(not item["optional"] for item in ingredients)
    prep = min(required * PREP_MINUTES_PER_INGREDIENT, MAX_PREP_MINUTES) if minutes else 0
    area = clean_text(meal.get("strArea"))
    cuisine = CUISINES.get(area, area)
    thumb = meal.get("strMealThumb") or ""
    return {
        "title": clean_title(meal.get("strMeal")),
        "description": None,
        "cuisine": cuisine[:50] if cuisine else None,
        "servings": GUESSED_SERVINGS,
        "prep_time": prep,
        "cook_time": minutes,
        "instructions": "\n".join(steps)[:10000],
        "ingredients": ingredients,
        "source_url": SOURCE_PREFIX + str(meal.get("idMeal")),
        "time_status": "estimated" if minutes else "unknown",
        "servings_estimated": True,
        # "/medium" is TheMealDB's smaller size: about 45 KB instead of 125 KB.
        "photo_url": f"{thumb}/medium" if thumb.startswith("https://") else None,
        "warnings": warnings,
    }


def fetch_catalog(fetch_bytes: Callable = fetch) -> list:
    """Every meal in TheMealDB, one request per first character."""
    meals = {}
    for character in FIRST_CHARACTERS:
        data = json.loads(fetch_bytes(f"{API}/search.php?f={character}", MAX_RESPONSE_BYTES))
        for meal in data.get("meals") or []:
            meals[meal["idMeal"]] = meal
    return list(meals.values())


def imported_urls(db: Session) -> set:
    query = select(Recipe.source_url).where(Recipe.source_url.startswith(SOURCE_PREFIX))
    return set(db.scalars(query))


def save_meals(db: Session, meals: list, fetch_bytes: Optional[Callable] = None, progress=None) -> dict:
    """Save every meal that isn't in the database yet. With fetch_bytes, download photos too.
    Returns counts, and the reason for each recipe that couldn't be saved."""
    have = imported_urls(db)
    result = {"added": 0, "already_there": 0, "photos": 0, "photo_failures": 0, "skipped": []}
    for meal in meals:
        fields = to_recipe(meal)
        if fields["source_url"] in have:
            result["already_there"] += 1
            continue
        try:
            data = RecipeCreate(**{k: v for k, v in fields.items() if k in RecipeCreate.model_fields})
        except ValidationError as error:
            result["skipped"].append(f"{fields['title'] or meal.get('idMeal')}: {error.errors()[0]['msg']}")
            continue
        recipe = recipe_service.create_recipe(db, data)
        recipe.time_status = fields["time_status"]
        recipe.servings_estimated = fields["servings_estimated"]
        db.commit()
        have.add(fields["source_url"])
        result["added"] += 1
        if fetch_bytes and fields["photo_url"]:
            try:
                photos.save_photo(db, recipe, fetch_bytes(fields["photo_url"], photos.MAX_BYTES))
                result["photos"] += 1
            except (ImportFailed, photos.InvalidPhotoError):
                result["photo_failures"] += 1
        if progress:
            progress(result["added"])
    return result


def remove_imported(db: Session) -> dict:
    """Take TheMealDB recipes out again, except ones pinned or cooked (they're yours now)."""
    result = {"removed": 0, "kept": 0}
    for recipe in db.scalars(select(Recipe).where(Recipe.source_url.startswith(SOURCE_PREFIX))).all():
        if recipe.pinned or recipe.times_cooked:
            result["kept"] += 1
            continue
        photo = recipe.photo_filename
        recipe_service.delete_recipe(db, recipe)
        photos.delete_file(photo)
        result["removed"] += 1
    return result
