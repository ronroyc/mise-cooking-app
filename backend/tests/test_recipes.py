"""Tests for the recipe API: create, read, update, delete, search, and validation."""
import pytest
from sqlalchemy import func, select

from app.models import Ingredient, RecipeIngredient


def make_recipe(**overrides):
    recipe = {
        "title": "Egg Fried Rice",
        "description": "Quick and simple.",
        "servings": 2,
        "prep_time": 5,
        "cook_time": 10,
        "cuisine": "Chinese",
        "instructions": "Scramble eggs.\nAdd rice.",
        "ingredients": [
            {"name": "rice", "quantity": 3, "unit": "cup"},
            {"name": "egg", "quantity": 2, "unit": "each", "preparation_note": "beaten"},
            {"name": "salt"},
        ],
    }
    recipe.update(overrides)
    return recipe


def create(client, **overrides):
    response = client.post("/api/recipes", json=make_recipe(**overrides))
    assert response.status_code == 201, response.json()
    return response.json()


# ---------- Create + read ----------

def test_create_recipe_returns_full_recipe(client):
    recipe = create(client)

    assert recipe["id"] > 0
    assert recipe["title"] == "Egg Fried Rice"
    assert recipe["total_time"] == 15
    assert [i["name"] for i in recipe["ingredients"]] == ["rice", "egg", "salt"]
    assert recipe["ingredients"][2]["quantity"] is None  # "to taste"


def test_get_recipe_by_id(client):
    created = create(client)

    response = client.get(f"/api/recipes/{created['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "Egg Fried Rice"


def test_get_missing_recipe_returns_404(client):
    response = client.get("/api/recipes/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Recipe not found"


def test_ingredient_names_are_normalized(client):
    recipe = create(client, ingredients=[{"name": "  Soy   SAUCE ", "quantity": 1, "unit": "TBSP"}])

    assert recipe["ingredients"][0]["name"] == "soy sauce"
    assert recipe["ingredients"][0]["unit"] == "tbsp"


def test_recipes_share_ingredient_rows(client, db):
    """Two recipes using 'egg' should point at the same row in the ingredients table."""
    create(client, title="Recipe A")
    create(client, title="Recipe B")

    egg_count = db.scalar(select(func.count()).select_from(Ingredient).where(Ingredient.name == "egg"))
    assert egg_count == 1


# ---------- Validation ----------

@pytest.mark.parametrize(
    "overrides",
    [
        {"title": ""},
        {"title": "   "},
        {"servings": 0},
        {"servings": -2},
        {"prep_time": -1},
        {"ingredients": []},
        {"ingredients": [{"name": "egg", "quantity": -1, "unit": "each"}]},
        {"ingredients": [{"name": "egg", "quantity": 0, "unit": "each"}]},
        {"ingredients": [{"name": ""}]},
        {"ingredients": [{"name": "salt", "unit": "tsp"}]},  # unit without quantity
    ],
    ids=[
        "empty title", "blank title", "zero servings", "negative servings", "negative prep time",
        "no ingredients", "negative quantity", "zero quantity", "empty ingredient name",
        "unit without quantity",
    ],
)
def test_invalid_recipes_are_rejected(client, overrides):
    response = client.post("/api/recipes", json=make_recipe(**overrides))

    assert response.status_code == 422
    # Errors come back as readable strings, not raw Pydantic objects.
    assert all(isinstance(message, str) for message in response.json()["detail"])


def test_duplicate_ingredients_are_rejected(client):
    response = client.post(
        "/api/recipes",
        json=make_recipe(ingredients=[{"name": "egg", "quantity": 1}, {"name": "Egg", "quantity": 2}]),
    )

    assert response.status_code == 422
    assert "listed more than once" in response.json()["detail"][0]


def test_validation_error_message_names_the_field(client):
    response = client.post("/api/recipes", json=make_recipe(servings=0))

    assert response.json()["detail"] == ["servings: Input should be greater than 0"]


# ---------- Update ----------

def test_patch_changes_only_sent_fields(client):
    created = create(client)

    response = client.patch(f"/api/recipes/{created['id']}", json={"title": "Better Fried Rice"})

    assert response.status_code == 200
    updated = response.json()
    assert updated["title"] == "Better Fried Rice"
    assert updated["servings"] == 2
    assert len(updated["ingredients"]) == 3


def test_patch_replaces_ingredient_list(client):
    created = create(client)

    # "egg" was already on the recipe, which is exactly the case that can break a unique constraint.
    new_ingredients = [
        {"name": "egg", "quantity": 4, "unit": "each"},
        {"name": "green onion", "quantity": 2, "unit": "each"},
    ]
    response = client.patch(f"/api/recipes/{created['id']}", json={"ingredients": new_ingredients})

    assert response.status_code == 200
    ingredients = response.json()["ingredients"]
    assert [(i["name"], i["quantity"]) for i in ingredients] == [("egg", 4), ("green onion", 2)]


def test_patch_rejects_null_for_required_field(client):
    created = create(client)

    response = client.patch(f"/api/recipes/{created['id']}", json={"title": None})

    assert response.status_code == 422


def test_patch_missing_recipe_returns_404(client):
    response = client.patch("/api/recipes/9999", json={"title": "Nope"})

    assert response.status_code == 404


# ---------- Delete ----------

def test_delete_recipe_removes_links_but_keeps_ingredients(client, db):
    created = create(client)

    response = client.delete(f"/api/recipes/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/recipes/{created['id']}").status_code == 404
    assert db.scalar(select(func.count()).select_from(RecipeIngredient)) == 0
    # Ingredients are shared, so they stay even when no recipe uses them.
    assert db.scalar(select(func.count()).select_from(Ingredient)) == 3


def test_delete_missing_recipe_returns_404(client):
    assert client.delete("/api/recipes/9999").status_code == 404


# ---------- List, search, filter ----------

@pytest.fixture
def three_recipes(client):
    create(client, title="Egg Fried Rice", cuisine="Chinese", prep_time=5, cook_time=10)
    create(
        client,
        title="Chicken Teriyaki",
        cuisine="japanese",
        prep_time=10,
        cook_time=20,
        description="Glossy and sweet.",
        ingredients=[{"name": "chicken thigh", "quantity": 1, "unit": "lb"}],
    )
    create(client, title="Butter Chicken", cuisine="Indian", prep_time=15, cook_time=30)


def titles(response):
    return [r["title"] for r in response.json()]


def test_list_is_sorted_by_title(client, three_recipes):
    response = client.get("/api/recipes")

    assert titles(response) == ["Butter Chicken", "Chicken Teriyaki", "Egg Fried Rice"]


def test_list_sorting_ignores_capitalization(client):
    """Regression test: SQLite's default sort put 'Chicken Teriyaki' before 'Chicken and Vegetable Stir-Fry'."""
    create(client, title="Chicken Teriyaki")
    create(client, title="Chicken and Vegetable Stir-Fry")

    assert titles(client.get("/api/recipes")) == ["Chicken and Vegetable Stir-Fry", "Chicken Teriyaki"]


def test_search_matches_title_case_insensitively(client, three_recipes):
    assert titles(client.get("/api/recipes?search=CHICKEN")) == ["Butter Chicken", "Chicken Teriyaki"]


def test_search_matches_description(client, three_recipes):
    assert titles(client.get("/api/recipes?search=glossy")) == ["Chicken Teriyaki"]


def test_search_matches_ingredient_name(client, three_recipes):
    assert titles(client.get("/api/recipes?search=thigh")) == ["Chicken Teriyaki"]


def test_search_treats_percent_sign_literally(client, three_recipes):
    assert titles(client.get("/api/recipes?search=%25")) == []


def test_filter_by_cuisine_is_case_insensitive(client, three_recipes):
    assert titles(client.get("/api/recipes?cuisine=JAPANESE")) == ["Chicken Teriyaki"]


def test_filter_by_max_total_time(client, three_recipes):
    assert titles(client.get("/api/recipes?max_total_time=30")) == ["Chicken Teriyaki", "Egg Fried Rice"]


def test_filters_combine(client, three_recipes):
    response = client.get("/api/recipes?search=chicken&max_total_time=30")

    assert titles(response) == ["Chicken Teriyaki"]


def test_negative_max_time_is_rejected(client):
    assert client.get("/api/recipes?max_total_time=-5").status_code == 422


def test_list_cuisines(client, three_recipes):
    # "japanese" was saved as "Japanese" because cuisines are title-cased.
    assert client.get("/api/recipes/cuisines").json() == ["Chinese", "Indian", "Japanese"]
