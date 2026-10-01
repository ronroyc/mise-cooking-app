"""Tests for the inventory API, expiration tracking, and the demo inventory seed."""
import json
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.database.seed import INVENTORY_SEED_FILE, SEED_FILE, seed_database, seed_inventory
from app.models import Ingredient, InventoryItem
from app.models.inventory import expiration_status


def days_from_now(days):
    return (date.today() + timedelta(days=days)).isoformat()


def add(client, **fields):
    item = {"name": "rice", "quantity": 4, "unit": "cup", "location": "pantry"}
    item.update(fields)
    response = client.post("/api/inventory", json=item)
    assert response.status_code == 201, response.json()
    return response.json()


# ---------- Expiration status ----------

TODAY = date(2026, 9, 25)


@pytest.mark.parametrize(
    "expires,expected",
    [
        (None, None),
        (TODAY - timedelta(days=1), "expired"),
        (TODAY, "expiring_soon"),
        (TODAY + timedelta(days=3), "expiring_soon"),
        (TODAY + timedelta(days=4), "fresh"),
    ],
    ids=["no date", "yesterday", "today", "in 3 days", "in 4 days"],
)
def test_expiration_status(expires, expected):
    assert expiration_status(expires, TODAY) == expected


# ---------- Create + read ----------

def test_add_item_returns_full_item(client):
    item = add(client, expiration_date=days_from_now(2))

    assert item["id"] > 0
    assert item["name"] == "rice"
    assert item["quantity"] == 4
    assert item["location"] == "pantry"
    assert item["days_until_expiration"] == 2
    assert item["expiration_status"] == "expiring_soon"


def test_item_without_quantity_or_date(client):
    item = add(client, name="salt", quantity=None, unit=None)

    assert item["quantity"] is None
    assert item["expiration_date"] is None
    assert item["expiration_status"] is None


def test_names_units_and_locations_are_normalized(client):
    item = add(client, name="  Soy   SAUCE ", unit="CUP", location="Fridge")

    assert item["name"] == "soy sauce"
    assert item["unit"] == "cup"
    assert item["location"] == "fridge"


def test_inventory_shares_ingredient_rows_with_recipes(client, db):
    """Inventory 'garlic' and recipe 'garlic' must be the same row, so matching is an id comparison."""
    client.post("/api/recipes", json={
        "title": "Garlic Rice", "servings": 2, "prep_time": 5, "cook_time": 15,
        "instructions": "Cook.", "ingredients": [{"name": "garlic", "quantity": 2, "unit": "clove"}],
    })
    add(client, name="Garlic", quantity=5, unit="clove")

    assert db.scalar(select(func.count()).select_from(Ingredient).where(Ingredient.name == "garlic")) == 1


def test_new_ingredient_gets_category(client):
    item = add(client, name="tahini", category="Sauces & Condiments")

    assert item["category"] == "Sauces & Condiments"


def test_get_item_by_id(client):
    created = add(client)

    response = client.get(f"/api/inventory/{created['id']}")

    assert response.status_code == 200
    assert response.json()["name"] == "rice"


def test_get_missing_item_returns_404(client):
    response = client.get("/api/inventory/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Inventory item not found"


def test_adding_same_ingredient_twice_is_a_conflict(client, db):
    add(client, name="egg", quantity=6, unit="each")

    response = client.post("/api/inventory", json={"name": "Egg", "quantity": 2, "unit": "each"})

    assert response.status_code == 409
    assert "already in your inventory" in response.json()["detail"]
    assert db.scalar(select(func.count()).select_from(InventoryItem)) == 1


# ---------- Validation ----------

@pytest.mark.parametrize(
    "fields",
    [
        {"name": ""},
        {"name": "   "},
        {"quantity": 0},
        {"quantity": -1},
        {"quantity": None, "unit": "cup"},
        {"location": "garage"},
        {"expiration_date": "not a date"},
        {"expiration_date": "2026-02-30"},
    ],
    ids=[
        "empty name", "blank name", "zero quantity", "negative quantity",
        "unit without quantity", "unknown location", "not a date", "impossible date",
    ],
)
def test_invalid_items_are_rejected(client, fields):
    item = {"name": "rice", "quantity": 4, "unit": "cup"}
    item.update(fields)

    response = client.post("/api/inventory", json=item)

    assert response.status_code == 422
    assert all(isinstance(message, str) for message in response.json()["detail"])


# ---------- List + filters ----------

def test_list_sorts_soonest_expiration_first_and_undated_last(client):
    add(client, name="salt", quantity=None, unit=None)
    add(client, name="milk", expiration_date=days_from_now(5))
    add(client, name="basil", expiration_date=days_from_now(1))
    add(client, name="black pepper", quantity=None, unit=None)

    names = [i["name"] for i in client.get("/api/inventory").json()]

    assert names == ["basil", "milk", "black pepper", "salt"]


def test_filter_by_location(client):
    add(client, name="rice", location="pantry")
    add(client, name="milk", location="fridge")

    names = [i["name"] for i in client.get("/api/inventory?location=fridge").json()]

    assert names == ["milk"]


def test_unknown_location_filter_is_rejected(client):
    assert client.get("/api/inventory?location=garage").status_code == 422


def test_search_by_name(client):
    add(client, name="soy sauce")
    add(client, name="fish sauce")
    add(client, name="rice")

    names = [i["name"] for i in client.get("/api/inventory?search=SAUCE").json()]

    assert sorted(names) == ["fish sauce", "soy sauce"]


def test_search_matches_percent_literally(client):
    add(client, name="rice")

    assert client.get("/api/inventory?search=%25").json() == []


def test_expires_within_includes_expired_but_not_undated(client):
    add(client, name="spinach", expiration_date=days_from_now(-2))
    add(client, name="milk", expiration_date=days_from_now(3))
    add(client, name="cheese", expiration_date=days_from_now(10))
    add(client, name="salt", quantity=None, unit=None)

    names = [i["name"] for i in client.get("/api/inventory?expires_within=3").json()]

    assert names == ["spinach", "milk"]


# ---------- Update ----------

def test_patch_changes_only_sent_fields(client):
    created = add(client, expiration_date=days_from_now(10))

    response = client.patch(f"/api/inventory/{created['id']}", json={"quantity": 2})

    assert response.status_code == 200
    updated = response.json()
    assert updated["quantity"] == 2
    assert updated["unit"] == "cup"
    assert updated["expiration_date"] == created["expiration_date"]


def test_patch_can_clear_expiration_date(client):
    created = add(client, expiration_date=days_from_now(10))

    updated = client.patch(f"/api/inventory/{created['id']}", json={"expiration_date": None}).json()

    assert updated["expiration_date"] is None
    assert updated["expiration_status"] is None


def test_patch_quantity_to_null_also_clears_unit(client):
    created = add(client)

    updated = client.patch(f"/api/inventory/{created['id']}", json={"quantity": None}).json()

    assert updated["quantity"] is None
    assert updated["unit"] is None


def test_patch_unit_onto_item_without_quantity_is_rejected(client):
    created = add(client, name="salt", quantity=None, unit=None)

    response = client.patch(f"/api/inventory/{created['id']}", json={"unit": "cup"})

    assert response.status_code == 422
    assert response.json()["detail"] == ["unit needs a quantity"]


def test_patch_rename(client):
    created = add(client, name="scallion")

    updated = client.patch(f"/api/inventory/{created['id']}", json={"name": "Green Onion"}).json()

    assert updated["name"] == "green onion"


def test_patch_rename_to_existing_item_is_a_conflict(client):
    add(client, name="egg")
    rice = add(client, name="rice")

    response = client.patch(f"/api/inventory/{rice['id']}", json={"name": "egg"})

    assert response.status_code == 409
    assert client.get(f"/api/inventory/{rice['id']}").json()["name"] == "rice"


@pytest.mark.parametrize("field", ["name", "location"])
def test_patch_cannot_null_required_fields(client, field):
    created = add(client)

    response = client.patch(f"/api/inventory/{created['id']}", json={field: None})

    assert response.status_code == 422


def test_patch_missing_item_returns_404(client):
    assert client.patch("/api/inventory/9999", json={"quantity": 1}).status_code == 404


# ---------- Delete ----------

def test_delete_item_keeps_ingredient(client, db):
    created = add(client, name="garlic")

    assert client.delete(f"/api/inventory/{created['id']}").status_code == 204
    assert client.get(f"/api/inventory/{created['id']}").status_code == 404
    assert db.scalar(select(func.count()).select_from(Ingredient).where(Ingredient.name == "garlic")) == 1


def test_delete_missing_item_returns_404(client):
    assert client.delete("/api/inventory/9999").status_code == 404


def test_deleting_recipe_keeps_inventory(client):
    recipe = client.post("/api/recipes", json={
        "title": "Plain Rice", "servings": 2, "prep_time": 0, "cook_time": 20,
        "instructions": "Cook.", "ingredients": [{"name": "rice", "quantity": 1, "unit": "cup"}],
    }).json()
    add(client, name="rice")

    client.delete(f"/api/recipes/{recipe['id']}")

    assert [i["name"] for i in client.get("/api/inventory").json()] == ["rice"]


# ---------- Ingredients (autocomplete) ----------

def test_list_ingredients_is_alphabetical(client):
    add(client, name="rice")
    add(client, name="basil")

    assert [i["name"] for i in client.get("/api/ingredients").json()] == ["basil", "rice"]


# ---------- Demo inventory seed ----------

def test_seed_inventory_loads_items_with_relative_dates(db):
    items = json.loads(INVENTORY_SEED_FILE.read_text())["items"]
    seed_database(db)

    added = seed_inventory(db, today=TODAY)

    assert added == len(items)
    spinach = db.scalar(select(InventoryItem).join(InventoryItem.ingredient).where(Ingredient.name == "spinach"))
    assert spinach.expiration_date == TODAY - timedelta(days=1)


def test_seed_inventory_does_not_duplicate(db):
    first = seed_inventory(db)
    second = seed_inventory(db)

    assert first > 0
    assert second == 0


def test_every_seeded_inventory_item_is_used_by_a_recipe():
    """Catches typos: demo inventory should line up with demo recipes for matching in M3."""
    recipe_names = {i["name"] for r in json.loads(SEED_FILE.read_text())["recipes"] for i in r["ingredients"]}
    inventory_names = {i["name"] for i in json.loads(INVENTORY_SEED_FILE.read_text())["items"]}

    assert inventory_names - recipe_names == set()
