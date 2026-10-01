"""Tests for recommendations: scoring, ordering, explanations, staples, and filters."""
from datetime import date, timedelta

import pytest


def create_recipe(client, title, ingredients, total_time=30, cuisine=None):
    body = {
        "title": title, "servings": 2, "prep_time": 0, "cook_time": total_time, "cuisine": cuisine,
        "instructions": "Cook it.", "ingredients": ingredients,
    }
    response = client.post("/api/recipes", json=body)
    assert response.status_code == 201, response.json()
    return response.json()


def stock(client, name, quantity=None, unit=None, expires_in=None):
    body = {"name": name, "quantity": quantity, "unit": unit}
    if expires_in is not None:
        body["expiration_date"] = (date.today() + timedelta(days=expires_in)).isoformat()
    response = client.post("/api/inventory", json=body)
    assert response.status_code == 201, response.json()


def recommend(client, **params):
    response = client.get("/api/recommendations", params=params)
    assert response.status_code == 200, response.json()
    return response.json()


def by_title(result):
    return {r["recipe"]["title"]: r for r in result["recommendations"]}


def test_empty_kitchen(client):
    create_recipe(client, "Rice", [{"name": "rice", "quantity": 1, "unit": "cup"}])

    result = recommend(client)

    assert result["inventory_count"] == 0
    rec = result["recommendations"][0]
    assert (rec["score"], rec["missing"]) == (0, ["rice"])
    assert rec["reasons"] == ["You have 0 of 1 ingredient.", "Missing rice."]


def test_score_parts(client):
    create_recipe(client, "Stir Fry", [
        {"name": "rice", "quantity": 1, "unit": "cup"},   # have: 1
        {"name": "egg", "quantity": 4, "unit": "each"},   # short: 0.5
        {"name": "ginger", "quantity": 1, "unit": "tbsp"},  # missing: 0
        {"name": "salt"},                                 # staple: 1
        {"name": "cilantro", "optional": True},           # doesn't count
    ])
    stock(client, "rice", 2, "cup")
    stock(client, "egg", 2, "each")

    rec = recommend(client)["recommendations"][0]

    # 2.5 of 4 required -> 70 * 0.625 = 43.75, rounded to 44. No ratings yet, so no taste points.
    assert (rec["coverage_points"], rec["use_soon_points"], rec["taste_points"], rec["score"]) == (44, 0, 0, 44)
    assert (rec["have_count"], rec["required_count"], rec["ready"]) == (2, 4, False)
    assert (rec["missing"], rec["short"]) == (["ginger"], ["egg"])
    assert rec["reasons"] == [
        "You have 2 of 4 ingredients.",
        "Not enough egg.",
        "Missing ginger.",
    ]


def test_ready_recipe_scores_70_and_says_so(client):
    create_recipe(client, "Rice", [{"name": "rice", "quantity": 1, "unit": "cup"}, {"name": "salt"}])
    stock(client, "rice", 2, "cup")

    rec = recommend(client)["recommendations"][0]

    assert (rec["score"], rec["ready"]) == (70, True)
    assert rec["reasons"] == ["You have everything you need."]


def test_expiring_items_add_points_and_a_reason(client):
    create_recipe(client, "Spinach Rice", [
        {"name": "rice", "quantity": 1, "unit": "cup"},
        {"name": "spinach", "quantity": 2, "unit": "cup"},
        {"name": "cream", "quantity": 1, "unit": "cup"},
    ])
    stock(client, "rice", 2, "cup", expires_in=30)
    stock(client, "spinach", expires_in=1)
    stock(client, "cream", expires_in=0)

    rec = recommend(client)["recommendations"][0]

    assert (rec["coverage_points"], rec["use_soon_points"], rec["score"]) == (70, 20, 90)
    assert rec["use_soon"] == ["cream", "spinach"]  # soonest first
    assert rec["reasons"][1:] == [
        "Uses your cream, expiring today.",
        "Uses your spinach, expiring tomorrow.",
    ]


def test_use_soon_points_are_capped(client):
    names = ["kale", "leek", "milk"]
    create_recipe(client, "Soup", [{"name": n} for n in names])
    for n in names:
        stock(client, n, expires_in=2)

    rec = recommend(client)["recommendations"][0]

    assert rec["use_soon_points"] == 20
    assert len(rec["use_soon"]) == 3


def test_expired_items_count_as_missing_and_earn_nothing(client):
    create_recipe(client, "Milk Toast", [{"name": "milk", "quantity": 1, "unit": "cup"}])
    stock(client, "milk", 1, "l", expires_in=-2)

    rec = recommend(client)["recommendations"][0]

    assert (rec["score"], rec["expired"], rec["use_soon"]) == (0, ["milk"], [])
    assert "Past its date: milk." in rec["reasons"]


def test_best_match_comes_first(client):
    create_recipe(client, "A Nothing", [{"name": "truffle"}])
    create_recipe(client, "B Half", [{"name": "rice"}, {"name": "truffle"}])
    create_recipe(client, "C All", [{"name": "rice"}])
    stock(client, "rice")

    titles = [r["recipe"]["title"] for r in recommend(client)["recommendations"]]

    assert titles == ["C All", "B Half", "A Nothing"]


def test_ties_go_to_fewer_missing_then_quicker(client):
    # Both 40 points: one has 1 of 2, the other 2 of 4 (more missing).
    create_recipe(client, "Two Missing", [{"name": "rice"}, {"name": "egg"}, {"name": "x1"}, {"name": "x2"}])
    create_recipe(client, "Slow", [{"name": "rice"}, {"name": "y1"}], total_time=90)
    create_recipe(client, "Quick", [{"name": "rice"}, {"name": "z1"}], total_time=10)
    stock(client, "rice")
    stock(client, "egg")

    titles = [r["recipe"]["title"] for r in recommend(client)["recommendations"]]

    assert titles == ["Quick", "Slow", "Two Missing"]


def test_long_missing_list_is_shortened(client):
    create_recipe(client, "Big", [{"name": n} for n in ["a1", "b1", "c1", "d1", "e1"]])

    rec = recommend(client)["recommendations"][0]

    assert "Missing a1, b1, c1, and 2 more." in rec["reasons"]


def test_filters_and_limit(client):
    create_recipe(client, "Quick Thai", [{"name": "rice"}], total_time=15, cuisine="Thai")
    create_recipe(client, "Slow Thai", [{"name": "rice"}], total_time=120, cuisine="Thai")
    create_recipe(client, "Quick Italian", [{"name": "pasta"}], total_time=15, cuisine="Italian")

    assert set(by_title(recommend(client, cuisine="thai"))) == {"Quick Thai", "Slow Thai"}
    assert set(by_title(recommend(client, max_total_time=30))) == {"Quick Thai", "Quick Italian"}
    assert set(by_title(recommend(client, search="pasta"))) == {"Quick Italian"}
    assert len(recommend(client, limit=1)["recommendations"]) == 1


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"max_total_time": -1}])
def test_bad_parameters(client, params):
    assert client.get("/api/recommendations", params=params).status_code == 422


def test_staples_are_assumed_unless_tracked(client):
    recipe = create_recipe(client, "Seasoned", [{"name": "salt"}, {"name": "black pepper"}, {"name": "water"}])

    statuses = [i["status"] for i in client.get(f"/api/recipes/{recipe['id']}/match").json()["ingredients"]]
    assert statuses == ["staple", "staple", "staple"]

    stock(client, "salt", expires_in=-1)  # tracked, and expired: the inventory wins
    statuses = [i["status"] for i in client.get(f"/api/recipes/{recipe['id']}/match").json()["ingredients"]]
    assert statuses == ["expired", "staple", "staple"]
