"""Tests for taste-based recommendations: learning what you like from your ratings."""
import pytest

from app.services.taste import MIN_LIKED_MEALS


def create_recipe(client, title, names):
    body = {"title": title, "servings": 2, "prep_time": 5, "cook_time": 10, "instructions": "Cook it.",
            "ingredients": [{"name": n} for n in names]}
    response = client.post("/api/recipes", json=body)
    assert response.status_code == 201, response.json()
    return response.json()


def cook(client, recipe, rating):
    response = client.post(f"/api/recipes/{recipe['id']}/cooked", json={"rating": rating, "update_inventory": False})
    assert response.status_code == 201, response.json()


def recs(client):
    return {r["recipe"]["title"]: r for r in client.get("/api/recommendations").json()["recommendations"]}


@pytest.fixture
def kitchen(client):
    """Three kinds of recipe; you love the garlicky one."""
    garlic = create_recipe(client, "Garlic Noodles", ["garlic", "soy sauce", "noodles"])
    create_recipe(client, "Garlic Bread", ["garlic", "butter", "bread"])
    create_recipe(client, "Garlic Fried Rice", ["garlic", "soy sauce", "rice", "egg"])
    create_recipe(client, "Pancakes", ["sugar", "flour", "milk"])
    create_recipe(client, "Plain Rice", ["rice", "water"])
    return garlic


def test_no_taste_points_until_enough_liked_meals(client, kitchen):
    for _ in range(MIN_LIKED_MEALS - 1):
        cook(client, kitchen, 5)

    assert all(r["taste_points"] == 0 for r in recs(client).values())
    assert client.get("/api/profile").json()["taste_needed"] == 1


def test_low_ratings_dont_count_as_liking(client, kitchen):
    for _ in range(5):
        cook(client, kitchen, 2)
    assert all(r["taste_points"] == 0 for r in recs(client).values())


def test_recipes_like_the_ones_you_love_rank_higher(client, kitchen):
    for _ in range(MIN_LIKED_MEALS):
        cook(client, kitchen, 5)

    result = recs(client)

    # Same salty, savory, garlicky direction as the loved noodles:
    assert result["Garlic Fried Rice"]["taste_points"] >= 8
    assert "Fits your taste" in " ".join(result["Garlic Fried Rice"]["reasons"])
    # Garlic, but buttery and creamy rather than salty and savory: not the same taste.
    assert result["Garlic Bread"]["taste_points"] < result["Garlic Fried Rice"]["taste_points"]
    assert result["Pancakes"]["taste_points"] == 0
    assert all(0 <= r["taste_points"] <= 10 for r in result.values())
    profile = client.get("/api/profile").json()
    assert set(profile["taste"]["likes"]) >= {"Salty", "Umami", "Garlicky"}
    assert profile["taste"]["liked_meals"] == MIN_LIKED_MEALS
    assert profile["taste_needed"] == 0


def test_the_kitchen_still_matters_more_than_taste(client, kitchen):
    for _ in range(MIN_LIKED_MEALS):
        cook(client, kitchen, 5)
    for name in ("rice",):  # Plain Rice: rice + water (a staple) -> ready to cook
        client.post("/api/inventory", json={"name": name, "quantity": 2, "unit": "cup"})

    result = recs(client)

    # Ready but not to your taste still beats to your taste but nothing on hand.
    assert result["Plain Rice"]["score"] > result["Garlic Bread"]["score"]
    ranking = [r["recipe"]["title"] for r in client.get("/api/recommendations").json()["recommendations"]]
    assert ranking[0] == "Plain Rice"
