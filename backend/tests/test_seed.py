"""Tests for the demo seed data."""
import json

from sqlalchemy import func, select

from app.database.seed import SEED_FILE, seed_database
from app.models import Ingredient, Recipe


def test_seed_loads_all_recipes(db):
    expected = len(json.loads(SEED_FILE.read_text())["recipes"])

    added = seed_database(db)

    assert added == expected
    assert db.scalar(select(func.count()).select_from(Recipe)) == expected


def test_seed_does_not_duplicate_when_run_twice(db):
    first = seed_database(db)
    second = seed_database(db)

    assert first > 0
    assert second == 0
    assert db.scalar(select(func.count()).select_from(Recipe)) == first


def test_every_seeded_ingredient_has_a_category(db):
    """Catches typos: an ingredient in a recipe that's missing from ingredient_categories."""
    seed_database(db)

    uncategorized = db.scalars(select(Ingredient.name).where(Ingredient.category.is_(None))).all()
    assert uncategorized == []


def test_every_listed_category_is_used_by_a_recipe(db):
    """Catches the opposite typo: a category entry no recipe actually uses."""
    data = json.loads(SEED_FILE.read_text())
    used = {i["name"] for r in data["recipes"] for i in r["ingredients"]}

    assert set(data["ingredient_categories"]) - used == set()
