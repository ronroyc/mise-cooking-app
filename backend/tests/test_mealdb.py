"""Tests for importing TheMealDB's catalog. No real network: fetching is replaced
with a function that returns saved data."""
import json

import pytest

from app.models import Recipe
from app.services import mealdb
from app.services.recipe_import import ImportFailed, parse_amount

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100


def meal(meal_id="52772", **overrides):
    """A TheMealDB meal, shaped like the API's (20 ingredient and measure slots)."""
    data = {
        "idMeal": meal_id,
        "strMeal": "Teriyaki Chicken Casserole",
        "strArea": "Japanese",
        "strCategory": "Chicken",
        "strInstructions": "STEP 1\r\nPreheat oven to 350° F.\r\n\r\n2. Simmer the sauce for 5 minutes.\r\n"
                           "▢ Bake 35 minutes or until cooked through.",
        "strMealThumb": "https://www.themealdb.com/images/media/meals/wvpsxx1468256321.jpg",
    }
    pairs = [("3/4 cup", "soy sauce"), ("2 cloves minced", "Garlic"), ("2", "Chicken Breasts"),
             ("Juice of 1", "Lemon"), ("To serve", "Parsley"), ("Pinch", "Salt")]
    for n in range(1, 21):
        measure, name = pairs[n - 1] if n <= len(pairs) else ("", "")
        data[f"strMeasure{n}"], data[f"strIngredient{n}"] = measure, name
    data.update(overrides)
    return data


# ---------- Amounts and ingredients ----------

@pytest.mark.parametrize("text, expected", [
    ("1 1/2 cups", (1.5, "cup", "")),
    ("100g", (100.0, "g", "")),
    ("85g/3oz", (85.0, "g", "")),
    ("3  tablespoons", (3.0, "tbsp", "")),
    ("2 tblsp", (2.0, "tbsp", "")),
    ("1 ½ tbsp", (1.5, "tbsp", "")),
    ("2-3", (3.0, None, "")),
    ("2 cloves minced", (2.0, "clove", "minced")),
    ("2 sprigs of fresh", (2.0, "sprig", "fresh")),
    ("Pinch", (None, None, "Pinch")),
    ("To taste", (None, None, "To taste")),
])
def test_parse_amount(text, expected):
    assert parse_amount(text) == expected


@pytest.mark.parametrize("measure, name, expected", [
    ("3/4 cup", "soy sauce", {"name": "soy sauce", "quantity": 0.75, "unit": "cup", "preparation_note": None}),
    ("2 cloves minced", "Garlic", {"name": "Garlic", "quantity": 2.0, "unit": "clove", "preparation_note": "minced"}),
    ("1", "chopped onion", {"name": "onion", "quantity": 1.0, "unit": None, "preparation_note": "chopped"}),
    ("Juice of 1/2", "Lemon", {"name": "Lemon", "quantity": 0.5, "unit": None, "preparation_note": "juice"}),
    ("Zest and juice of one", "lime", {"name": "lime", "quantity": 1, "unit": None, "preparation_note": "zest and juice"}),
    ("Pinch", "Salt", {"name": "Salt", "quantity": None, "unit": None, "preparation_note": "pinch"}),
    ("1 (12 oz.)", "stir-fry vegetables",
     {"name": "stir-fry vegetables", "quantity": 1.0, "unit": None, "preparation_note": "12 oz."}),
])
def test_parse_pair(measure, name, expected):
    item = mealdb.parse_pair(measure, name)
    assert {k: item[k] for k in expected} == expected


def test_garnish_is_optional():
    assert mealdb.parse_pair("To serve", "Parsley")["optional"] is True
    assert mealdb.parse_pair("Garnish", "coriander")["optional"] is True
    assert mealdb.parse_pair("1 tbsp", "soy sauce")["optional"] is False


def test_ingredient_listed_twice_is_merged():
    ingredients, warnings = mealdb.parse_ingredients(
        meal(strMeasure1="100g", strIngredient1="Butter", strMeasure2="50g", strIngredient2="butter")
    )
    butter = [i for i in ingredients if i["name"].lower() == "butter"]
    assert len(butter) == 1 and butter[0]["quantity"] == 150
    assert warnings == []


# ---------- Steps and times ----------

def test_steps_drop_labels_and_numbers():
    assert mealdb.parse_steps("STEP 1\r\nHeat the oil.\r\n\r\n2. Add rice.\n▢ Stir.\n3\nServe.") == [
        "Heat the oil.", "Add rice.", "Stir.", "Serve.",
    ]


@pytest.mark.parametrize("steps, minutes", [
    (["Bake 35 minutes.", "Simmer for 20 mins."], 55),
    (["Rest for 1-2 hours."], 120),
    (["Bake for 1 1/2 hours, then cool for half an hour."], 120),
    (["Cook for a minute, then about an hour more."], 61),
    (["Mix well and serve."], 0),
    (["Chill for 48 hours."], 1440),  # the most a recipe can say
])
def test_estimate_minutes(steps, minutes):
    assert mealdb.estimate_minutes(steps) == minutes


def test_to_recipe():
    recipe = mealdb.to_recipe(meal())
    assert recipe["title"] == "Teriyaki Chicken Casserole"
    assert recipe["cuisine"] == "Japanese"
    assert recipe["instructions"] == "Preheat oven to 350° F.\nSimmer the sauce for 5 minutes.\n" \
                                     "Bake 35 minutes or until cooked through."
    assert recipe["cook_time"] == 40
    assert recipe["prep_time"] == 10  # 5 required ingredients (parsley is optional), 2 minutes each
    assert recipe["time_status"] == "estimated"
    assert recipe["servings"] == 4 and recipe["servings_estimated"] is True
    assert recipe["source_url"] == "https://www.themealdb.com/meal/52772"
    assert recipe["photo_url"].endswith(".jpg/medium")


def test_no_times_in_the_steps_is_unknown():
    recipe = mealdb.to_recipe(meal(strInstructions="Mix everything.\nServe."))
    assert recipe["time_status"] == "unknown"
    assert recipe["prep_time"] == 0 and recipe["cook_time"] == 0


@pytest.mark.parametrize("title, cleaned", [
    ("Achiote Oil (Aceite Achiotado) Recipe", "Achiote Oil (Aceite Achiotado)"),
    ("Ají de Aguacate Recipe (Colombian Spicy Avocado Sauce)", "Ají de Aguacate (Colombian Spicy Avocado Sauce)"),
    ("Recipe Box Pancakes", "Recipe Box Pancakes"),
])
def test_clean_title(title, cleaned):
    assert mealdb.clean_title(title) == cleaned


@pytest.mark.parametrize("area, cuisine", [("France", "French"), ("United States", "American"),
                                           ("Thai", "Thai"), ("Unknown", None), (None, None)])
def test_cuisine_names(area, cuisine):
    assert mealdb.to_recipe(meal(strArea=area))["cuisine"] == cuisine


# ---------- Fetching and saving ----------

def fake_fetch(responses):
    def fetch(url, max_bytes):
        if url not in responses:
            raise ImportFailed("not found")
        return responses[url]
    return fetch


def test_fetch_catalog_asks_for_every_first_character():
    asked = []

    def fetch(url, max_bytes):
        asked.append(url)
        found = [meal("1"), meal("2")] if url.endswith("f=t") else [meal("2")] if url.endswith("f=c") else None
        return json.dumps({"meals": found}).encode()

    meals = mealdb.fetch_catalog(fetch)
    assert len(asked) == 36
    assert sorted(m["idMeal"] for m in meals) == ["1", "2"]  # meal 2 came twice, kept once


def test_save_meals(db, photos_dir):
    fetch = fake_fetch({meal()["strMealThumb"] + "/medium": JPEG})
    result = mealdb.save_meals(db, [meal(), meal("2", strMealThumb="https://example.com/missing.jpg")], fetch)
    assert result["added"] == 2 and result["photos"] == 1 and result["photo_failures"] == 1

    recipe = db.query(Recipe).filter_by(source_url="https://www.themealdb.com/meal/52772").one()
    assert recipe.time_status == "estimated" and recipe.servings_estimated is True
    assert {i.name for i in recipe.ingredients} >= {"soy sauce", "garlic", "chicken breasts", "lemon"}
    assert (photos_dir / recipe.photo_filename).read_bytes() == JPEG

    # Running it again adds nothing.
    again = mealdb.save_meals(db, [meal(), meal("2")])
    assert again["added"] == 0 and again["already_there"] == 2


def test_save_meals_skips_invalid(db):
    result = mealdb.save_meals(db, [meal(strInstructions=""), meal("2")])
    assert result["added"] == 1
    assert result["skipped"][0].startswith("Teriyaki Chicken Casserole:")


def test_remove_keeps_pinned_and_cooked(client, db):
    mealdb.save_meals(db, [meal("1"), meal("2"), meal("3")])
    ids = [r.id for r in db.query(Recipe).order_by(Recipe.id)]
    client.put(f"/api/recipes/{ids[0]}/pin")
    client.post(f"/api/recipes/{ids[1]}/cooked", json={"update_inventory": False})
    db.expire_all()
    assert mealdb.remove_imported(db) == {"removed": 1, "kept": 2}


# ---------- Estimated times in the rest of the app ----------

def test_unknown_time_is_left_out_of_time_filter(client, db):
    mealdb.save_meals(db, [meal("1"), meal("2", strInstructions="Mix.\nServe.")])
    statuses = {r["time_status"] for r in client.get("/api/recipes", params={"max_total_time": 600}).json()}
    assert statuses == {"estimated"}
    assert len(client.get("/api/recipes").json()) == 2


def test_api_shows_estimates(client, db):
    mealdb.save_meals(db, [meal()])
    recipe = client.get("/api/recipes").json()[0]
    assert recipe["time_status"] == "estimated" and recipe["servings_estimated"] is True


def test_editing_times_or_servings_replaces_the_estimate(client, db):
    mealdb.save_meals(db, [meal()])
    recipe_id = client.get("/api/recipes").json()[0]["id"]

    # The form sends every field: unchanged values keep the estimate.
    same = client.patch(f"/api/recipes/{recipe_id}", json={"title": "Casserole", "prep_time": 10, "cook_time": 40,
                                                            "servings": 4}).json()
    assert same["time_status"] == "estimated" and same["servings_estimated"] is True

    changed = client.patch(f"/api/recipes/{recipe_id}", json={"cook_time": 50, "servings": 6}).json()
    assert changed["time_status"] is None and changed["servings_estimated"] is False


def test_hand_typed_recipes_have_no_estimates(client):
    from tests.test_recipes import make_recipe
    created = client.post("/api/recipes", json=make_recipe()).json()
    assert created["time_status"] is None and created["servings_estimated"] is False
