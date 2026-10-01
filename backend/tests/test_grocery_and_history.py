"""Tests for the grocery list, cooking history, and ratings."""
from datetime import date, timedelta

import pytest


def create_recipe(client, ingredients, title="Test Dish", servings=2):
    body = {
        "title": title, "servings": servings, "prep_time": 5, "cook_time": 10,
        "instructions": "Cook it.", "ingredients": ingredients,
    }
    response = client.post("/api/recipes", json=body)
    assert response.status_code == 201, response.json()
    return response.json()


def stock(client, name, quantity=None, unit=None, **fields):
    response = client.post("/api/inventory", json={"name": name, "quantity": quantity, "unit": unit, **fields})
    assert response.status_code == 201, response.json()
    return response.json()


def add(client, name, quantity=None, unit=None):
    response = client.post("/api/grocery", json={"name": name, "quantity": quantity, "unit": unit})
    assert response.status_code == 201, response.json()
    return response.json()


def grocery(client):
    return client.get("/api/grocery").json()


def inventory(client):
    return {i["name"]: i for i in client.get("/api/inventory").json()}


# ---------- Grocery list ----------

def test_add_and_list(client):
    item = add(client, "Rice", 2, "cups")

    assert (item["name"], item["quantity"], item["unit"], item["checked"]) == ("rice", 2, "cup", False)
    assert (item["amount_text"], item["quantity_text"]) == ("2 cups", "2 cups")
    assert add(client, "egg", 6)["quantity_text"] == "6"
    assert [i["name"] for i in grocery(client)] == ["egg", "rice"]


def test_list_as_text_for_reminders(client):
    add(client, "rice", 2, "cups")
    add(client, "salt")
    bought = add(client, "egg", 6)
    client.patch(f"/api/grocery/{bought['id']}", json={"checked": True})

    response = client.get("/api/grocery/text")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text.splitlines() == ["Rice (2 cups)", "Salt"]  # checked items left out


def test_empty_list_as_text(client):
    assert client.get("/api/grocery/text").text == ""


def test_same_ingredient_is_combined(client):
    add(client, "butter", 1, "cup")
    add(client, "butter", 4, "tbsp")  # = 1/4 cup

    items = grocery(client)

    assert len(items) == 1
    assert items[0]["amount_text"] == "1 1/4 cups"


def test_plural_combines_with_singular(client):
    add(client, "egg", 2, "each")
    add(client, "eggs", 3)

    assert [(i["name"], i["quantity"]) for i in grocery(client)] == [("egg", 5)]


def test_amounts_that_dont_convert_stay_separate(client):
    add(client, "flour", 2, "lb")
    add(client, "flour", 1, "cup")

    assert sorted(i["amount_text"] for i in grocery(client)) == ["1 cup", "2 lb"]


def test_some_then_amount(client):
    add(client, "salt")
    add(client, "salt", 1, "lb")

    items = grocery(client)
    assert len(items) == 1 and items[0]["amount_text"] == "1 lb"


def test_checked_items_are_not_combined_and_sort_last(client):
    first = add(client, "rice", 2, "cup")
    client.patch(f"/api/grocery/{first['id']}", json={"checked": True})
    add(client, "rice", 1, "cup")
    add(client, "apple", 1)

    items = grocery(client)

    assert [(i["name"], i["checked"]) for i in items] == [("apple", False), ("rice", False), ("rice", True)]


def test_grouped_by_store_section(client):
    create_recipe(client, [{"name": "spinach"}, {"name": "rice"}])  # just to create the ingredients
    client.post("/api/inventory", json={"name": "zucchini", "category": "Produce"})
    for name in ["rice", "zucchini", "unknown thing"]:
        add(client, name)

    names = [i["name"] for i in grocery(client)]

    assert names[-1] == "unknown thing"  # no category goes last


def test_update_and_delete(client):
    item = add(client, "milk", 1, "l")

    changed = client.patch(f"/api/grocery/{item['id']}", json={"quantity": 2}).json()
    assert changed["amount_text"] == "2 l"
    some = client.patch(f"/api/grocery/{item['id']}", json={"quantity": None}).json()
    assert (some["quantity"], some["unit"]) == (None, None)
    assert client.patch(f"/api/grocery/{item['id']}", json={"unit": "cup"}).status_code == 422

    assert client.delete(f"/api/grocery/{item['id']}").status_code == 204
    assert grocery(client) == []
    assert client.delete(f"/api/grocery/{item['id']}").status_code == 404


@pytest.mark.parametrize(
    "body",
    [{"name": ""}, {"name": "rice", "quantity": 0}, {"name": "rice", "unit": "cup"}, {"name": "rice", "quantity": -1}],
)
def test_bad_items_are_rejected(client, body):
    assert client.post("/api/grocery", json=body).status_code == 422


def test_add_from_recipe(client):
    recipe = create_recipe(client, [
        {"name": "rice", "quantity": 2, "unit": "cup"},       # have enough: skipped
        {"name": "egg", "quantity": 4, "unit": "each"},       # have 1: add 3
        {"name": "ginger", "quantity": 1, "unit": "tbsp"},    # missing: add all
        {"name": "milk", "quantity": 1, "unit": "cup"},       # expired: add all
        {"name": "salt"},                                     # staple: skipped
        {"name": "cilantro", "optional": True},               # optional: skipped
    ], title="Congee")
    stock(client, "rice", 5, "cup")
    stock(client, "egg", 1, "each")
    stock(client, "milk", 1, "l", expiration_date=(date.today() - timedelta(days=1)).isoformat())

    result = client.post(f"/api/grocery/from-recipe/{recipe['id']}").json()

    assert {i["name"]: i["amount_text"] for i in result["added"]} == {"egg": "3 eggs", "ginger": "1 tbsp", "milk": "1 cup"}
    assert result["skipped_optional"] == 1
    assert result["message"] == "Added 3 items to your grocery list. Skipped 1 optional ingredient."
    assert all(i["for_recipes"] == "Congee" for i in result["added"])


def test_add_from_recipe_scaled_and_twice(client):
    recipe = create_recipe(client, [{"name": "ginger", "quantity": 1, "unit": "tbsp"}], title="Tea", servings=2)
    other = create_recipe(client, [{"name": "ginger", "quantity": 1, "unit": "tsp"}], title="Soup")

    client.post(f"/api/grocery/from-recipe/{recipe['id']}?servings=4")
    client.post(f"/api/grocery/from-recipe/{other['id']}")
    items = grocery(client)

    assert len(items) == 1
    assert (items[0]["amount_text"], items[0]["for_recipes"]) == ("2 1/3 tbsp", "Tea, Soup")


def test_add_from_recipe_when_nothing_is_needed(client):
    recipe = create_recipe(client, [{"name": "rice", "quantity": 1, "unit": "cup"}])
    stock(client, "rice", 1, "cup")

    result = client.post(f"/api/grocery/from-recipe/{recipe['id']}").json()

    assert (result["added"], result["message"]) == ([], "You already have everything this recipe needs.")


def test_add_from_unknown_recipe_is_404(client):
    assert client.post("/api/grocery/from-recipe/999").status_code == 404


def test_stock_checked_items(client):
    client.post("/api/inventory", json={"name": "spinach", "category": "Produce"})
    client.delete(f"/api/inventory/{inventory(client)['spinach']['id']}")  # known ingredient, not stocked
    stock(client, "rice", 1, "cup")
    stock(client, "milk", 1, "cup", expiration_date=(date.today() - timedelta(days=3)).isoformat())
    stock(client, "flour", 2, "lb")
    for name, quantity, unit in [("spinach", 5, "oz"), ("rice", 2, "cup"), ("milk", 1, "l"),
                                 ("flour", 1, "cup"), ("salt", None, None)]:
        item = add(client, name, quantity, unit)
        client.patch(f"/api/grocery/{item['id']}", json={"checked": True})
    unchecked = add(client, "apples", 3)

    messages = client.post("/api/grocery/stock-checked").json()["messages"]
    kitchen = inventory(client)

    assert messages == [
        "Added spinach (5 oz) to your fridge.",
        "Added 2 cups to your rice; you now have 3 cups.",
        "Replaced your expired milk with 1 l.",
        "Couldn't add 1 cup to your flour (2 lb): the units don't convert. Update the amount on the Inventory page.",
        "Added salt (some) to your pantry.",
    ]
    assert (kitchen["spinach"]["location"], kitchen["spinach"]["amount_text"]) == ("fridge", "5 oz")
    assert kitchen["rice"]["quantity"] == 3
    assert (kitchen["milk"]["amount_text"], kitchen["milk"]["expiration_date"]) == ("1 l", None)
    assert kitchen["flour"]["amount_text"] == "2 lb"
    assert [i["id"] for i in grocery(client)] == [unchecked["id"]]


def test_clear_checked(client):
    item = add(client, "rice")
    add(client, "beans")
    client.patch(f"/api/grocery/{item['id']}", json={"checked": True})

    assert client.delete("/api/grocery/checked").json() == {"removed": 1}
    assert [i["name"] for i in grocery(client)] == ["beans"]
    assert inventory(client) == {}  # cleared, not stocked


# ---------- Cooking history ----------

def test_log_cooked_subtracts_from_inventory(client):
    recipe = create_recipe(client, [
        {"name": "rice", "quantity": 2, "unit": "cup"},
        {"name": "egg", "quantity": 3, "unit": "each"},
        {"name": "butter", "quantity": 2, "unit": "tbsp"},
        {"name": "flour", "quantity": 1, "unit": "cup"},
        {"name": "soy sauce", "quantity": 1, "unit": "tbsp"},
        {"name": "salt"},
        {"name": "cilantro", "quantity": 1, "unit": "tbsp", "optional": True},
    ], title="Fried Rice")
    stock(client, "rice", 5, "cup")
    stock(client, "eggs", 3)
    stock(client, "butter", 0.5, "cup")
    stock(client, "flour", 2, "lb")
    stock(client, "soy sauce")
    stock(client, "cilantro", 1, "bunch")

    response = client.post(f"/api/recipes/{recipe['id']}/cooked", json={"rating": 4, "notes": "Good"})
    result = response.json()
    kitchen = inventory(client)

    assert response.status_code == 201
    assert (result["log"]["recipe_title"], result["log"]["servings"], result["log"]["rating"]) == ("Fried Rice", 2, 4)
    assert result["log"]["cooked_on"] == date.today().isoformat()
    assert result["inventory_changes"] == [
        "Used 2 cups rice; 3 cups left.",
        "Used up your egg, so it's off the inventory.",  # "eggs" was stocked as the recipe's "egg"
        "Used 2 tbsp butter; 6 tbsp left.",
        "Left your flour as is: 1 cup doesn't convert to lb.",
    ]
    assert "egg" not in kitchen
    assert kitchen["butter"]["quantity"] == pytest.approx(0.375)
    assert kitchen["soy sauce"]["amount_text"] == "some"  # "some" is left alone
    assert kitchen["cilantro"]["amount_text"] == "1 bunch"  # optional is left alone


def test_log_cooked_scaled(client):
    recipe = create_recipe(client, [{"name": "rice", "quantity": 1, "unit": "cup"}], servings=2)
    stock(client, "rice", 5, "cup")

    result = client.post(f"/api/recipes/{recipe['id']}/cooked", json={"servings": 6}).json()

    assert result["log"]["servings"] == 6
    assert inventory(client)["rice"]["quantity"] == 2


def test_log_cooked_without_touching_inventory(client):
    recipe = create_recipe(client, [{"name": "rice", "quantity": 1, "unit": "cup"}])
    stock(client, "rice", 5, "cup")

    result = client.post(f"/api/recipes/{recipe['id']}/cooked", json={"update_inventory": False}).json()

    assert result["inventory_changes"] == []
    assert inventory(client)["rice"]["quantity"] == 5


@pytest.mark.parametrize(
    "body",
    [{"rating": 0}, {"rating": 6}, {"servings": 0}, {"cooked_on": (date.today() + timedelta(days=1)).isoformat()}],
)
def test_log_cooked_rejects_bad_input(client, body):
    recipe = create_recipe(client, [{"name": "rice"}])

    assert client.post(f"/api/recipes/{recipe['id']}/cooked", json=body).status_code == 422


def test_log_cooked_unknown_recipe_is_404(client):
    assert client.post("/api/recipes/999/cooked", json={}).status_code == 404


def test_recipe_stats_and_history(client):
    recipe = create_recipe(client, [{"name": "rice"}], title="Rice")
    other = create_recipe(client, [{"name": "beans"}], title="Beans")
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    client.post(f"/api/recipes/{recipe['id']}/cooked", json={"rating": 5, "cooked_on": week_ago})
    client.post(f"/api/recipes/{recipe['id']}/cooked", json={"rating": 4})
    client.post(f"/api/recipes/{recipe['id']}/cooked", json={})
    client.post(f"/api/recipes/{other['id']}/cooked", json={})

    stats = client.get(f"/api/recipes/{recipe['id']}").json()
    history = client.get("/api/history").json()
    only_rice = client.get(f"/api/history?recipe_id={recipe['id']}").json()

    assert (stats["times_cooked"], stats["last_cooked"], stats["average_rating"]) == (3, date.today().isoformat(), 4.5)
    assert history[-1]["cooked_on"] == week_ago  # newest first
    assert len(history) == 4 and len(only_rice) == 3
    listed = {r["title"]: r for r in client.get("/api/recipes").json()}
    assert listed["Beans"]["times_cooked"] == 1 and listed["Beans"]["average_rating"] is None


def test_rate_later_and_delete(client):
    recipe = create_recipe(client, [{"name": "rice"}])
    log = client.post(f"/api/recipes/{recipe['id']}/cooked", json={}).json()["log"]

    rated = client.patch(f"/api/history/{log['id']}", json={"rating": 3, "notes": "  "}).json()
    assert (rated["rating"], rated["notes"]) == (3, None)
    cleared = client.patch(f"/api/history/{log['id']}", json={"rating": None}).json()
    assert cleared["rating"] is None
    assert client.patch(f"/api/history/{log['id']}", json={"cooked_on": None}).status_code == 422

    assert client.delete(f"/api/history/{log['id']}").status_code == 204
    assert client.get("/api/history").json() == []
    assert client.delete(f"/api/history/{log['id']}").status_code == 404


def test_deleting_a_recipe_keeps_its_history(client):
    recipe = create_recipe(client, [{"name": "rice"}], title="Gone Soon")
    client.post(f"/api/recipes/{recipe['id']}/cooked", json={"rating": 5})

    client.delete(f"/api/recipes/{recipe['id']}")
    history = client.get("/api/history").json()

    assert [(h["recipe_id"], h["recipe_title"], h["rating"]) for h in history] == [(None, "Gone Soon", 5)]
