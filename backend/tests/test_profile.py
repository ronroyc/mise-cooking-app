"""Tests for flavor profiles and the profile page's data."""
from types import SimpleNamespace

import pytest

from app.services.flavors import FLAVORS, flavor_of_ingredient, level, recipe_flavor


def item(name, optional=False):
    return SimpleNamespace(name=name, optional=optional)


def create_recipe(client, title, ingredients, cuisine=None, minutes=15):
    body = {"title": title, "servings": 2, "prep_time": 5, "cook_time": minutes - 5, "cuisine": cuisine,
            "instructions": "Cook it.", "ingredients": [{"name": n} for n in ingredients]}
    response = client.post("/api/recipes", json=body)
    assert response.status_code == 201, response.json()
    return response.json()


def cook(client, recipe, rating=None):
    response = client.post(f"/api/recipes/{recipe['id']}/cooked", json={"rating": rating, "update_inventory": False})
    assert response.status_code in (200, 201), response.json()


def flavor_value(profile, flavor):
    return next(v["value"] for v in profile["flavor"]["values"] if v["flavor"] == flavor)


# ---------- Flavors ----------

def test_one_strong_ingredient_makes_a_strong_flavor():
    result = recipe_flavor([item("garlic"), item("rice")])
    assert result["values"]["garlicky"] == pytest.approx(0.95)
    assert result["because"]["garlicky"] == ["garlic"]
    assert result["unknown"] == []  # rice is known, just neutral


def test_flavors_add_up_but_never_pass_one():
    two = recipe_flavor([item("soy sauce"), item("fish sauce")])["values"]["salty"]
    assert two == pytest.approx(1 - 0.1 * 0.1)
    assert all(0 <= v <= 1 for v in two and recipe_flavor([item("salt")] * 20)["values"].values())


def test_optional_and_unknown_ingredients():
    result = recipe_flavor([item("chili", optional=True), item("unicorn dust")])
    assert result["values"]["heat"] == 0
    assert result["unknown"] == ["unicorn dust"]


@pytest.mark.parametrize("name,expected", [
    ("salted butter", "butter"), ("Red Pepper Flakes", "red pepper flake"), ("salmon fillet", "salmon"),
    ("miso paste", "miso"), ("ground cumin", "cumin"), ("chow mein noodles", "noodle"), ("scallions", "green onion"),
])
def test_lookup_by_ending_beginning_and_synonym(name, expected):
    assert flavor_of_ingredient(name) == flavor_of_ingredient(expected)
    assert flavor_of_ingredient(name) is not None


def test_levels():
    assert [level(v) for v in (0.9, 0.6, 0.4, 0.2, 0.05)] == ["Very high", "High", "Medium", "Low", "Very low"]


def test_recipe_flavor_endpoint(client):
    recipe = create_recipe(client, "Garlic Noodles", ["garlic", "soy sauce", "noodles", "mystery sauce"])

    body = client.get(f"/api/recipes/{recipe['id']}/flavor").json()

    garlicky = next(v for v in body["values"] if v["flavor"] == "garlicky")
    assert (garlicky["label"], garlicky["level"], garlicky["because"]) == ("Garlicky", "Very high", ["garlic"])
    assert [v["flavor"] for v in body["values"]] == list(FLAVORS)
    assert body["unknown"] == ["mystery sauce"]
    assert client.get("/api/recipes/999/flavor").status_code == 404


# ---------- The profile ----------

def test_empty_profile_says_what_it_needs(client):
    body = client.get("/api/profile").json()

    assert body["stats"]["meals_cooked"] == 0
    assert body["stats"]["average_rating"] is None
    assert body["flavor"] is None
    assert "Cook or pin 3 more recipes" in body["flavor_missing"]
    assert body["observations"] == []
    assert body["observations_needed"] == 5


def test_flavor_profile_from_pins_and_meals(client):
    spicy = create_recipe(client, "Spicy", ["chili", "rice"])
    sweet = create_recipe(client, "Sweet", ["honey", "rice"])
    client.put(f"/api/recipes/{spicy['id']}/pin")
    client.put(f"/api/recipes/{sweet['id']}/pin")
    assert client.get("/api/profile").json()["flavor"] is None  # 2 sources isn't enough

    cook(client, spicy, rating=5)
    body = client.get("/api/profile").json()

    assert body["flavor"]["basis"] == ("Based on 1 meal you cooked and 2 recipes you pinned. "
                                       "Meals you rated higher count more.")
    # Pins count 1 each; the 5-star spicy meal counts 5/3.
    assert flavor_value(body, "heat") == pytest.approx(0.8 * (1 + 5 / 3) / (2 + 5 / 3), abs=0.001)
    assert flavor_value(body, "heat") > flavor_value(body, "sweet")


def test_stats(client):
    quick = create_recipe(client, "Quick", ["egg"], cuisine="Japanese", minutes=10)
    slow = create_recipe(client, "Slow", ["beef"], cuisine="Korean", minutes=50)
    cook(client, quick, rating=4)
    cook(client, quick, rating=5)
    cook(client, slow)

    stats = client.get("/api/profile").json()["stats"]

    assert stats["meals_cooked"] == 3
    assert stats["different_recipes"] == 2
    assert (stats["meals_rated"], stats["average_rating"]) == (2, 4.5)
    assert stats["average_minutes"] == round((10 + 10 + 50) / 3)
    assert stats["top_cuisine"] == {"name": "Japanese", "meals": 2}


def test_ingredients_come_from_meals_once_there_are_three(client):
    a = create_recipe(client, "A", ["garlic", "salt", "rice"])
    b = create_recipe(client, "B", ["garlic", "black pepper", "egg"])
    create_recipe(client, "Never cooked", ["egg", "egg noodles"])

    before = client.get("/api/profile").json()["ingredients"]
    assert before["source"] == "recipes"

    for recipe in (a, b, a):
        cook(client, recipe)
    after = client.get("/api/profile").json()["ingredients"]

    assert after["source"] == "meals"
    assert after["items"][0] == {"name": "garlic", "count": 3}
    assert "salt" not in [i["name"] for i in after["items"]]  # staples are left out
    assert "black pepper" not in [i["name"] for i in after["items"]]


def test_no_observations_until_five_meals(client):
    recipe = create_recipe(client, "Garlic Rice", ["garlic", "rice"], cuisine="Korean")
    for _ in range(4):
        cook(client, recipe, rating=5)
    body = client.get("/api/profile").json()
    assert body["observations"] == []
    assert body["observations_needed"] == 1


def test_observations_with_enough_data(client):
    garlic = create_recipe(client, "Garlic Noodles", ["garlic", "noodles"], cuisine="Chinese", minutes=15)
    plain = create_recipe(client, "Plain Rice Bowl", ["rice", "egg"], cuisine="Chinese", minutes=60)
    for rating in (5, 5, 4, 5):
        cook(client, garlic, rating=rating)
    for rating in (2, 3, 2):
        cook(client, plain, rating=rating)

    titles = [o["title"] for o in client.get("/api/profile").json()["observations"]]

    assert "Your go-to is Garlic Noodles." in titles
    assert "You cook a lot of Chinese food." in titles
    assert "Quick recipes rate higher for you." in titles
    assert "You like garlicky food." in titles


def test_deleted_recipes_still_count_as_meals(client):
    recipe = create_recipe(client, "Gone", ["garlic"])
    cook(client, recipe, rating=3)
    client.delete(f"/api/recipes/{recipe['id']}")

    body = client.get("/api/profile").json()

    assert body["stats"]["meals_cooked"] == 1
    assert body["flavor"] is None  # no ingredients left to taste


def test_observations_are_few_and_readable(client):
    spicy = create_recipe(client, "Chili Rice", ["chili", "rice"], minutes=15)
    creamy = create_recipe(client, "Cream Pasta", ["heavy cream", "pasta"], minutes=45)
    for rating in (5, 5, 5, 4):
        cook(client, spicy, rating=rating)
    for rating in (2, 2, 3):
        cook(client, creamy, rating=rating)

    observations = client.get("/api/profile").json()["observations"]
    titles = [o["title"] for o in observations]

    assert len(observations) <= 5
    assert "You like spicy food." in titles  # "spicy", not "heat food"
    assert "Creamy food isn't your favorite." in titles
    assert sum("isn't your favorite" in t for t in titles) == 1
