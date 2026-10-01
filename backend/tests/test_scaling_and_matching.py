"""Tests for recipe scaling (?servings=), ingredient matching (/match), and name-key reuse."""
from datetime import date, timedelta

import pytest

from app.schemas.recipe import RecipeOut
from app.services import matching


def create_recipe(client, ingredients, servings=4):
    body = {
        "title": "Test Dish", "servings": servings, "prep_time": 5, "cook_time": 10,
        "instructions": "Cook it.", "ingredients": ingredients,
    }
    response = client.post("/api/recipes", json=body)
    assert response.status_code == 201, response.json()
    return response.json()


def stock(client, name, quantity=None, unit=None, **fields):
    response = client.post("/api/inventory", json={"name": name, "quantity": quantity, "unit": unit, **fields})
    assert response.status_code == 201, response.json()
    return response.json()


def by_name(items):
    return {i["name"]: i for i in items}


# ---------- Display text ----------

def test_ingredients_come_with_display_text(client):
    recipe = create_recipe(client, [
        {"name": "rice", "quantity": 1.5, "unit": "Cups"},
        {"name": "egg", "quantity": 2, "unit": "each"},
        {"name": "garlic", "quantity": 3, "unit": "cloves"},
        {"name": "salt"},
    ])
    items = by_name(recipe["ingredients"])

    assert items["rice"]["unit"] == "cup"  # "Cups" was stored as "cup"
    assert items["rice"]["amount_text"] == "1 1/2 cups"
    assert (items["egg"]["amount_text"], items["egg"]["display_name"]) == ("2", "eggs")
    assert items["garlic"]["amount_text"] == "3 cloves"
    assert (items["salt"]["amount_text"], items["salt"]["display_name"]) == ("", "salt")


def test_inventory_amount_text(client):
    assert stock(client, "egg", 6, "each")["amount_text"] == "6 eggs"
    assert stock(client, "milk", 0.5, "gallons")["amount_text"] == "1/2 gallon"
    assert stock(client, "salt")["amount_text"] == "some"


# ---------- Scaling ----------

def test_scale_recipe(client):
    recipe = create_recipe(client, [
        {"name": "rice", "quantity": 2, "unit": "cup"},
        {"name": "soy sauce", "quantity": 1, "unit": "tbsp"},
        {"name": "egg", "quantity": 3, "unit": "each"},
        {"name": "salt"},
    ], servings=4)

    scaled = client.get(f"/api/recipes/{recipe['id']}?servings=2").json()
    items = by_name(scaled["ingredients"])

    assert (scaled["servings"], scaled["base_servings"]) == (2, 4)
    assert (items["rice"]["quantity"], items["rice"]["unit"]) == (1, "cup")
    assert items["soy sauce"]["amount_text"] == "1 1/2 tsp"  # 1/2 tbsp reads better as teaspoons
    assert (items["egg"]["amount_text"], items["egg"]["display_name"]) == ("1 1/2", "eggs")
    assert items["salt"]["quantity"] is None  # "to taste" doesn't scale


def test_scale_up_moves_to_bigger_units(client):
    recipe = create_recipe(client, [{"name": "butter", "quantity": 2, "unit": "tbsp"}], servings=2)

    scaled = client.get(f"/api/recipes/{recipe['id']}?servings=12").json()

    assert scaled["ingredients"][0]["amount_text"] == "3/4 cup"  # 12 tbsp


def test_original_size_is_unchanged(client):
    recipe = create_recipe(client, [{"name": "butter", "quantity": 4, "unit": "tbsp"}], servings=2)

    same = client.get(f"/api/recipes/{recipe['id']}?servings=2").json()

    # Not rewritten as 1/4 cup: at its own size, the recipe reads as written.
    assert same["ingredients"][0]["amount_text"] == "4 tbsp"
    assert same == client.get(f"/api/recipes/{recipe['id']}").json()


@pytest.mark.parametrize("servings", [0, -1, 101, "two"])
def test_scale_rejects_bad_servings(client, servings):
    recipe = create_recipe(client, [{"name": "rice", "quantity": 1, "unit": "cup"}])

    assert client.get(f"/api/recipes/{recipe['id']}?servings={servings}").status_code == 422


def test_scaling_does_not_change_the_saved_recipe(client):
    recipe = create_recipe(client, [{"name": "rice", "quantity": 2, "unit": "cup"}], servings=4)
    client.get(f"/api/recipes/{recipe['id']}?servings=8")

    saved = client.get(f"/api/recipes/{recipe['id']}").json()

    assert (saved["servings"], saved["ingredients"][0]["quantity"]) == (4, 2)


# ---------- Matching ----------

def test_match_statuses(client):
    today = date.today()
    recipe = create_recipe(client, [
        {"name": "rice", "quantity": 2, "unit": "cup"},        # have plenty
        {"name": "eggs", "quantity": 3, "unit": "each"},       # have only 2
        {"name": "milk", "quantity": 1, "unit": "cup"},        # expired
        {"name": "scallions", "quantity": 2, "unit": "each"},  # have (stocked as "green onion")
        {"name": "flour", "quantity": 1, "unit": "cup"},       # have, but by weight
        {"name": "soy sauce", "quantity": 2, "unit": "tbsp"},  # have "some"
        {"name": "salt"},                                      # to taste
        {"name": "ginger", "quantity": 1, "unit": "tbsp"},     # missing
        {"name": "cilantro", "optional": True},                # missing, optional
    ])
    stock(client, "rice", 4, "cups")
    stock(client, "egg", 2, "each")
    stock(client, "milk", 1, "l", expiration_date=(today - timedelta(days=1)).isoformat())
    stock(client, "green onion", 5)
    stock(client, "flour", 2, "lb")
    stock(client, "soy sauce")
    stock(client, "salt", 1, "lb")

    result = client.get(f"/api/recipes/{recipe['id']}/match").json()
    items = by_name(result["ingredients"])

    assert {name: i["status"] for name, i in items.items()} == {
        "rice": "have", "eggs": "short", "milk": "expired", "scallions": "have", "flour": "have",
        "soy sauce": "have", "salt": "have", "ginger": "missing", "cilantro": "missing",
    }
    # The recipe came first, so stocking "egg" and "green onion" reused its rows.
    assert items["scallions"]["inventory_name"] == "scallions"
    assert items["eggs"]["note"] == "You have 2 eggs; this needs 3 eggs."
    assert items["flour"]["note"] == "You have 2 lb; this needs 1 cup. Check it's enough."
    assert items["rice"]["inventory_amount_text"] == "4 cups"
    assert items["ginger"]["inventory_item_id"] is None
    # 8 required ingredients (cilantro is optional); rice, scallions, flour, soy sauce, salt are "have".
    assert (result["required_count"], result["have_count"], result["ready"]) == (8, 5, False)


def test_match_converts_units(client):
    recipe = create_recipe(client, [{"name": "butter", "quantity": 6, "unit": "tbsp"}])
    stock(client, "butter", 0.5, "cup")  # = 8 tbsp

    item = client.get(f"/api/recipes/{recipe['id']}/match").json()["ingredients"][0]

    assert item["status"] == "have"


def test_match_uses_scaled_amounts(client):
    recipe = create_recipe(client, [{"name": "rice", "quantity": 2, "unit": "cup"}], servings=2)
    stock(client, "rice", 3, "cup")

    normal = client.get(f"/api/recipes/{recipe['id']}/match").json()
    doubled = client.get(f"/api/recipes/{recipe['id']}/match?servings=4").json()

    assert normal["ready"] is True
    assert doubled["servings"] == 4
    assert doubled["ingredients"][0]["status"] == "short"
    assert doubled["ingredients"][0]["note"] == "You have 3 cups; this needs 4 cups."


def test_match_ready_when_everything_is_there(client):
    recipe = create_recipe(client, [{"name": "rice", "quantity": 1, "unit": "cup"}, {"name": "salt"}])
    stock(client, "rice", 1, "cup")
    stock(client, "salt")

    assert client.get(f"/api/recipes/{recipe['id']}/match").json()["ready"] is True


def test_match_unknown_recipe_is_404(client):
    assert client.get("/api/recipes/999/match").status_code == 404


def test_match_many_recipes_loads_inventory_once(db, client):
    # M4 will score every recipe; the inventory lookup should be shareable.
    first = create_recipe(client, [{"name": "rice", "quantity": 1, "unit": "cup"}])
    stock(client, "rice", 1, "cup")
    inventory = matching.inventory_by_key(db)
    recipe = RecipeOut.model_validate(client.get(f"/api/recipes/{first['id']}").json())

    assert matching.match_recipe(db, recipe, inventory=inventory).ready is True


# ---------- Same ingredient, different spelling ----------

def test_plural_reuses_existing_ingredient(client):
    create_recipe(client, [{"name": "egg", "quantity": 2, "unit": "each"}])
    recipe = create_recipe(client, [{"name": "Eggs", "quantity": 3, "unit": "each"}])

    assert recipe["ingredients"][0]["name"] == "egg"
    assert [i["name"] for i in client.get("/api/ingredients").json()] == ["egg"]


def test_recipe_rejects_same_ingredient_twice_with_different_spelling(client):
    body = {
        "title": "Eggs Eggs", "servings": 1, "prep_time": 1, "cook_time": 1, "instructions": "x",
        "ingredients": [{"name": "egg"}, {"name": "eggs"}],
    }
    response = client.post("/api/recipes", json=body)

    assert response.status_code == 422
    assert "'egg' and 'eggs' are listed more than once" in str(response.json())


def test_duplicate_inventory_item_reports_the_existing_one(client):
    existing = stock(client, "egg", 6, "each")

    response = client.post("/api/inventory", json={"name": "Eggs", "quantity": 12})

    assert response.status_code == 409
    assert response.json()["existing_id"] == existing["id"]
    assert "'egg' is already in your inventory" in response.json()["detail"]


def test_rename_to_a_synonym_keeps_the_new_name(client):
    item = stock(client, "scallion", 3)

    renamed = client.patch(f"/api/inventory/{item['id']}", json={"name": "green onion"}).json()

    assert renamed["name"] == "green onion"
