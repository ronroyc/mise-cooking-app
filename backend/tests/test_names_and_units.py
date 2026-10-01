"""Tests for ingredient-name matching (services/names.py) and units (services/units.py)."""
import json

import pytest

from app.database.seed import SEED_FILE
from app.services.names import match_key
from app.services.units import (
    convert, describe_amount, format_amount, format_quantity, normalize_unit, pluralize_name, tidy,
)


# ---------- Name matching ----------

@pytest.mark.parametrize(
    "a,b",
    [
        ("egg", "eggs"),
        ("egg", "Large Eggs"),
        ("egg", "extra-large eggs"),
        ("tomato", "tomatoes"),
        ("cherry tomato", "cherry tomatoes"),
        ("berry", "berries"),
        ("peach", "peaches"),
        ("bay leaf", "bay leaves"),
        ("cookie", "cookies"),
        ("chickpeas", "chickpea"),
        ("chickpeas", "garbanzo beans"),
        ("green onion", "scallions"),
        ("green onion", "spring onion"),
        ("all-purpose flour", "All Purpose Flour"),
        ("all-purpose flour", "plain flour"),
        ("confectioners' sugar", "powdered sugar"),
        ("thai chili", "Thai chilies"),
        ("thai chili", "thai chilli"),
        ("red pepper flakes", "chili flakes"),
        ("basil", "fresh basil"),
        ("olive oil", "extra virgin olive oil"),
        ("plain yogurt", "plain yoghurt"),
    ],
)
def test_same_ingredient(a, b):
    assert match_key(a) == match_key(b)


@pytest.mark.parametrize(
    "a,b",
    [
        ("basil", "thai basil"),
        ("coriander", "ground coriander"),
        ("cumin", "ground cumin"),
        ("chicken breast", "chicken thigh"),
        ("milk", "whole wheat flour"),
        ("pepper", "bell pepper"),
    ],
)
def test_different_ingredients(a, b):
    assert match_key(a) != match_key(b)


@pytest.mark.parametrize("word", ["molasses", "hummus", "asparagus", "couscous", "swiss"])
def test_words_ending_in_s_that_arent_plural(word):
    assert match_key(word) == word


def test_seed_ingredients_stay_distinct():
    # If two seed ingredients got the same key, one would silently swallow the other.
    recipes = json.loads(SEED_FILE.read_text())["recipes"]
    names = {i["name"].lower() for r in recipes for i in r["ingredients"]}
    keys = {}
    for name in names:
        assert match_key(name) not in keys, f"{name!r} collides with {keys[match_key(name)]!r}"
        keys[match_key(name)] = name


# ---------- Units ----------

@pytest.mark.parametrize(
    "typed,stored",
    [
        ("Tablespoons", "tbsp"), ("tbs", "tbsp"), ("teaspoon", "tsp"), ("CUPS", "cup"),
        ("pounds", "lb"), ("lbs", "lb"), ("ounces", "oz"), ("Grams", "g"), ("litres", "l"),
        ("fluid  ounces", "fl oz"), ("cloves", "clove"), ("pieces", "each"), ("whole", "each"),
        ("sprig", "sprig"), ("", None), ("   ", None), (None, None),
    ],
)
def test_normalize_unit(typed, stored):
    assert normalize_unit(typed) == stored


@pytest.mark.parametrize(
    "quantity,from_unit,to_unit,expected",
    [
        (3, "tsp", "tbsp", 1),
        (16, "tbsp", "cup", 1),
        (1, "cup", "ml", 236.588),
        (1, "lb", "oz", 16),
        (1, "kg", "lb", 2.20462),
        (2, None, "each", 2),
        (2, "clove", "clove", 2),
    ],
)
def test_convert(quantity, from_unit, to_unit, expected):
    assert convert(quantity, from_unit, to_unit) == pytest.approx(expected, rel=1e-4)


@pytest.mark.parametrize(
    "from_unit,to_unit",
    [("cup", "lb"), ("oz", "cup"), ("clove", "each"), ("can", "oz"), ("each", "g"), ("sprig", "bunch")],
)
def test_convert_refuses_different_kinds(from_unit, to_unit):
    assert convert(1, from_unit, to_unit) is None


@pytest.mark.parametrize(
    "quantity,unit,expected",
    [
        (6, "tsp", (2, "tbsp")),
        (12, "tbsp", (0.75, "cup")),
        (0.125, "cup", (2, "tbsp")),
        (4.5, "tbsp", (4.5, "tbsp")),  # 0.28 cup isn't a clean amount
        (5, "tbsp", (5, "tbsp")),
        (6, "tbsp", (6, "tbsp")),  # not 3/8 cup: no such measuring cup
        (0.5, "tsp", (0.5, "tsp")),
        (24, "oz", (1.5, "lb")),
        (0.25, "lb", (4, "oz")),
        (1500, "g", (1.5, "kg")),
        (3, "clove", (3, "clove")),
        (2, None, (2, None)),
    ],
)
def test_tidy(quantity, unit, expected):
    value, new_unit = tidy(quantity, unit)
    assert (pytest.approx(value, rel=1e-3), new_unit) == expected


@pytest.mark.parametrize(
    "quantity,unit,expected",
    [
        (2, "cup", "2"), (1.5, "cup", "1 1/2"), (0.333, "cup", "1/3"), (0.6667, "cup", "2/3"),
        (0.25, "tsp", "1/4"), (2.99, "cup", "3"), (0.05, "tsp", "0.05"),
        (250.0, "g", "250"), (1.25, "kg", "1.25"), (7.5, "ml", "7.5"),
    ],
)
def test_format_quantity(quantity, unit, expected):
    assert format_quantity(quantity, unit) == expected


@pytest.mark.parametrize(
    "quantity,unit,expected",
    [
        (1, "cup", "1 cup"), (1.5, "cup", "1 1/2 cups"), (3, "clove", "3 cloves"),
        (2, "tbsp", "2 tbsp"), (2, "each", "2"), (2, None, "2"), (None, None, ""),
    ],
)
def test_format_amount(quantity, unit, expected):
    assert format_amount(quantity, unit) == expected


@pytest.mark.parametrize(
    "name,quantity,unit,expected",
    [
        ("egg", 2, "each", "eggs"), ("egg", 1, "each", "egg"), ("tomato", 3, None, "tomatoes"),
        ("bell pepper", 2, "each", "bell peppers"), ("peach", 2, "each", "peaches"),
        ("cherry", 2, "each", "cherries"), ("avocado", 2, "each", "avocados"),
        ("rice", 2, "cup", "rice"), ("chickpeas", 2, "each", "chickpeas"), ("salt", None, None, "salt"),
    ],
)
def test_pluralize_name(name, quantity, unit, expected):
    assert pluralize_name(name, quantity, unit) == expected


def test_describe_amount():
    assert describe_amount(6, "each", "egg") == "6 eggs"
    assert describe_amount(1.5, "cup", "rice") == "1 1/2 cups"
    assert describe_amount(None, None, "salt") == "some"
