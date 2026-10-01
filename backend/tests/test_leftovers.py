"""Tests for saving leftovers when logging a cooked meal."""
from datetime import date, timedelta

from app.services.history import LEFTOVER_DAYS


def create_recipe(client, title="Chicken Fried Rice"):
    body = {"title": title, "servings": 4, "prep_time": 5, "cook_time": 10, "instructions": "Cook it.",
            "ingredients": [{"name": "rice", "quantity": 2, "unit": "cup"}]}
    response = client.post("/api/recipes", json=body)
    assert response.status_code == 201, response.json()
    return response.json()


def cook(client, recipe, **fields):
    response = client.post(f"/api/recipes/{recipe['id']}/cooked", json={"update_inventory": False, **fields})
    assert response.status_code == 201, response.json()
    return response.json()


def leftovers(client):
    return [i for i in client.get("/api/inventory").json() if i["name"].startswith("leftover ")]


def test_leftovers_go_in_the_fridge(client):
    recipe = create_recipe(client)

    result = cook(client, recipe, leftover_servings=2)

    [item] = leftovers(client)
    good_until = date.today() + timedelta(days=LEFTOVER_DAYS)
    assert (item["name"], item["quantity"], item["unit"], item["location"]) == (
        "leftover chicken fried rice", 2, "serving", "fridge")
    assert item["expiration_date"] == good_until.isoformat()
    assert result["inventory_changes"] == [
        f"Saved 2 servings of Chicken Fried Rice as leftovers in the fridge, good until {good_until:%b %-d}."]


def test_no_leftovers_unless_asked(client):
    cook(client, create_recipe(client))
    assert leftovers(client) == []


def test_leftovers_count_from_the_day_it_was_cooked(client):
    two_days_ago = date.today() - timedelta(days=2)

    cook(client, create_recipe(client), cooked_on=two_days_ago.isoformat(), leftover_servings=1)

    [item] = leftovers(client)
    assert item["expiration_date"] == (two_days_ago + timedelta(days=LEFTOVER_DAYS)).isoformat()
    assert item["expiration_status"] == "expiring_soon"  # shows under "Use soon"


def test_too_old_to_save(client):
    long_ago = date.today() - timedelta(days=LEFTOVER_DAYS + 1)

    result = cook(client, create_recipe(client), cooked_on=long_ago.isoformat(), leftover_servings=2)

    assert leftovers(client) == []
    assert "Didn't save leftovers" in result["inventory_changes"][0]


def test_more_leftovers_of_the_same_recipe_add_up_and_keep_the_earlier_date(client):
    recipe = create_recipe(client)
    yesterday = date.today() - timedelta(days=1)
    cook(client, recipe, cooked_on=yesterday.isoformat(), leftover_servings=1)

    result = cook(client, recipe, leftover_servings=2)

    [item] = leftovers(client)
    assert item["quantity"] == 3
    assert item["expiration_date"] == (yesterday + timedelta(days=LEFTOVER_DAYS)).isoformat()
    assert "3 servings in the fridge" in result["inventory_changes"][0]


def test_expired_leftovers_are_replaced(client):
    recipe = create_recipe(client)
    expired = client.post("/api/inventory", json={
        "name": "leftover chicken fried rice", "quantity": 5, "unit": "serving", "location": "fridge",
        "expiration_date": (date.today() - timedelta(days=1)).isoformat()})
    assert expired.status_code == 201, expired.json()

    cook(client, recipe, leftover_servings=2)

    [item] = leftovers(client)
    assert item["quantity"] == 2
    assert item["expiration_date"] == (date.today() + timedelta(days=LEFTOVER_DAYS)).isoformat()


def test_leftover_servings_must_be_sensible(client):
    recipe = create_recipe(client)
    for bad in (0, -1, 51):
        response = client.post(f"/api/recipes/{recipe['id']}/cooked", json={"leftover_servings": bad})
        assert response.status_code == 422
