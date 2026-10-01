"""Tests for meal prep: one shopping list and "prep together" steps for several recipes."""
from datetime import date, timedelta

import pytest


def create_recipe(client, title, ingredients, servings=2):
    body = {"title": title, "servings": servings, "prep_time": 5, "cook_time": 10, "instructions": "Cook it.",
            "ingredients": ingredients}
    response = client.post("/api/recipes", json=body)
    assert response.status_code == 201, response.json()
    return response.json()


def ing(name, quantity=None, unit=None, note=None, optional=False):
    return {"name": name, "quantity": quantity, "unit": unit, "preparation_note": note, "optional": optional}


def stock(client, name, quantity=None, unit=None, **fields):
    response = client.post("/api/inventory", json={"name": name, "quantity": quantity, "unit": unit, **fields})
    assert response.status_code == 201, response.json()


def plan(client, *recipes, servings=None):
    body = {"recipes": [{"id": r["id"], "servings": servings} for r in recipes]}
    response = client.post("/api/meal-prep/plan", json=body)
    assert response.status_code == 200, response.json()
    return response.json()


def shopping(result):
    return {s["name"]: s for s in result["shopping"]}


def test_recipes_share_the_inventory_instead_of_each_counting_it(client):
    a = create_recipe(client, "Fried Rice", [ing("rice", 1, "cup")])
    b = create_recipe(client, "Rice Bowl", [ing("rice", 1, "cup")])
    stock(client, "rice", 1.5, "cups")
    # Each recipe on its own is covered...
    assert client.get(f"/api/recipes/{a['id']}/match").json()["ready"] is True

    result = plan(client, a, b)

    # ...but together they need 2 cups, so half a cup is missing.
    rice = shopping(result)["rice"]
    assert rice["amount_text"] == "1/2 cup"
    assert rice["recipes"] == ["Fried Rice", "Rice Bowl"]
    assert rice["reason"] == "You have 1 1/2 cups; together they need 2 cups."


def test_missing_ingredients_are_added_up(client):
    a = create_recipe(client, "A", [ing("butter", 2, "tbsp"), ing("egg", 2)])
    b = create_recipe(client, "B", [ing("butter", 0.25, "cup"), ing("eggs", 3)])

    items = shopping(plan(client, a, b))

    assert items["butter"]["amount_text"] == "6 tbsp"
    assert items["egg"]["amount_text"] == "5 eggs"
    assert items["egg"]["reason"] is None


def test_units_that_dont_convert_stay_separate(client):
    a = create_recipe(client, "A", [ing("garlic", 3, "clove")])
    b = create_recipe(client, "B", [ing("garlic", 1, "tbsp")])

    assert shopping(plan(client, a, b))["garlic"]["amount_text"] == "3 cloves + 1 tbsp"


def test_staples_optional_and_covered(client):
    a = create_recipe(client, "A", [ing("salt"), ing("parsley", 2, "tbsp", optional=True), ing("oil", 1, "tbsp")])
    stock(client, "oil", 2, "cups")

    result = plan(client, a)

    assert result["shopping"] == []
    assert result["covered"] == ["oil", "salt"]  # parsley is optional, so it isn't planned at all


def test_expired_items_count_as_missing(client):
    a = create_recipe(client, "A", [ing("milk", 1, "cup")])
    stock(client, "milk", 1, "gallon", expiration_date=(date.today() - timedelta(days=1)).isoformat())

    milk = shopping(plan(client, a))["milk"]

    assert milk["amount_text"] == "1 cup"
    assert milk["reason"] == "Yours is past its date."


def test_servings_scale_the_plan(client):
    a = create_recipe(client, "A", [ing("rice", 1, "cup")], servings=2)

    result = plan(client, a, servings=6)

    assert shopping(result)["rice"]["amount_text"] == "3 cups"
    assert result["total_servings"] == 6


def test_prep_together(client):
    a = create_recipe(client, "Fried Rice", [
        ing("rice", 2, "cup", "cooked"), ing("garlic", 2, "clove", "minced"), ing("soy sauce", 1, "tbsp")])
    b = create_recipe(client, "Stir-Fry", [
        ing("rice", 1, "cup"), ing("garlic", 3, "clove", "finely minced"), ing("soy sauce", 2, "tbsp")])
    c = create_recipe(client, "Salad", [ing("green onion", 2, note="thinly sliced")])

    steps = {s["name"]: s for s in plan(client, a, b, c)["prep_together"]}

    assert steps["rice"]["instruction"] == "Cook 3 cups rice once"
    assert steps["garlic"]["instruction"] == "Mince 5 cloves garlic once"
    assert steps["garlic"]["recipes"] == ["Fried Rice", "Stir-Fry"]
    assert "soy sauce" not in steps  # nothing to do ahead: you just measure it
    assert "green onion" not in steps  # only one recipe uses it


def test_add_plan_to_grocery_list(client):
    a = create_recipe(client, "Fried Rice", [ing("rice", 1, "cup"), ing("egg", 2)])
    b = create_recipe(client, "Rice Bowl", [ing("rice", 1, "cup")])
    client.post("/api/grocery", json={"name": "rice", "quantity": 1, "unit": "cup"})  # already on the list

    response = client.post("/api/meal-prep/grocery", json={"recipes": [{"id": a["id"]}, {"id": b["id"]}]})

    assert response.status_code == 200, response.json()
    items = {i["name"]: i for i in client.get("/api/grocery").json()}
    assert items["rice"]["amount_text"] == "3 cups"  # combined with what was already listed
    assert items["rice"]["for_recipes"] == "Fried Rice, Rice Bowl"
    assert items["egg"]["amount_text"] == "2 eggs"


@pytest.mark.parametrize("body,status", [
    ({"recipes": []}, 422),
    ({"recipes": [{"id": 1}, {"id": 1}]}, 422),
    ({"recipes": [{"id": 999}]}, 404),
    ({"recipes": [{"id": 1, "servings": 0}]}, 422),
])
def test_bad_plans(client, body, status):
    create_recipe(client, "A", [ing("rice", 1, "cup")])
    assert client.post("/api/meal-prep/plan", json=body).status_code == status


def test_different_cuts_say_prep(client):
    a = create_recipe(client, "A", [ing("garlic", 2, "clove", "minced")])
    b = create_recipe(client, "B", [ing("garlic", 4, "clove", "thinly sliced")])

    [step] = plan(client, a, b)["prep_together"]

    assert step["instruction"] == "Prep 6 cloves garlic once"
    assert step["notes"] == ["minced", "thinly sliced"]
