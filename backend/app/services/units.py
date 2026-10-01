"""Units: cleaning up what people type, converting, and showing amounts nicely.

    normalize_unit("Tablespoons")  -> "tbsp"
    convert(3, "tsp", "tbsp")      -> 1.0
    convert(1, "cup", "lb")        -> None   (volume vs weight needs a density; not attempted)
    tidy(6, "tsp")                 -> (2.0, "tbsp")
    format_amount(1.5, "cup")      -> "1 1/2 cups"

Units Mise doesn't know ("sprig", "handful") are kept as typed. They still work,
they just only compare with the exact same unit.
"""
from fractions import Fraction
from typing import Optional

# What people type -> the one spelling Mise stores.
ALIASES = {
    "teaspoon": "tsp", "teaspoons": "tsp", "tsp": "tsp", "tsps": "tsp", "t": "tsp",
    "tablespoon": "tbsp", "tablespoons": "tbsp", "tbsp": "tbsp", "tbsps": "tbsp", "tbs": "tbsp", "tbl": "tbsp",
    "cup": "cup", "cups": "cup", "c": "cup",
    "fluid ounce": "fl oz", "fluid ounces": "fl oz", "fl oz": "fl oz", "fl. oz": "fl oz", "fl. oz.": "fl oz",
    "pint": "pint", "pints": "pint", "pt": "pint",
    "quart": "quart", "quarts": "quart", "qt": "quart",
    "gallon": "gallon", "gallons": "gallon", "gal": "gallon",
    "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "millilitres": "ml", "ml": "ml",
    "liter": "l", "liters": "l", "litre": "l", "litres": "l", "l": "l",
    "gram": "g", "grams": "g", "g": "g", "gr": "g",
    "kilogram": "kg", "kilograms": "kg", "kg": "kg", "kgs": "kg",
    "ounce": "oz", "ounces": "oz", "oz": "oz", "oz.": "oz",
    "pound": "lb", "pounds": "lb", "lb": "lb", "lbs": "lb", "lb.": "lb", "lbs.": "lb",
    "each": "each", "ea": "each", "whole": "each", "piece": "each", "pieces": "each", "pc": "each", "pcs": "each",
    "clove": "clove", "cloves": "clove",
    "can": "can", "cans": "can",
    "pinch": "pinch", "pinches": "pinch",
    "slice": "slice", "slices": "slice",
    "bunch": "bunch", "bunches": "bunch",
    "stick": "stick", "sticks": "stick",
    "package": "package", "packages": "package", "pkg": "package",
    "jar": "jar", "jars": "jar",
    "bottle": "bottle", "bottles": "bottle",
    "head": "head", "heads": "head",
    "sprig": "sprig", "sprigs": "sprig",
    "stalk": "stalk", "stalks": "stalk",
    "dash": "dash", "dashes": "dash",
    "handful": "handful", "handfuls": "handful",
    "sheet": "sheet", "sheets": "sheet",
    "serving": "serving", "servings": "serving",
}

# Size of each unit in a base unit: milliliters for volume, grams for weight.
VOLUME_ML = {
    "tsp": 4.92892, "tbsp": 14.7868, "fl oz": 29.5735, "cup": 236.588,
    "pint": 473.176, "quart": 946.353, "gallon": 3785.41, "ml": 1.0, "l": 1000.0,
}
WEIGHT_G = {"g": 1.0, "kg": 1000.0, "oz": 28.3495, "lb": 453.592}

# Plural forms for display. Abbreviations (tbsp, oz, lb, g...) don't change.
PLURALS = {
    "cup": "cups", "pint": "pints", "quart": "quarts", "gallon": "gallons",
    "clove": "cloves", "can": "cans", "pinch": "pinches", "slice": "slices", "bunch": "bunches",
    "stick": "sticks", "package": "packages", "jar": "jars", "bottle": "bottles", "head": "heads",
    "sprig": "sprigs", "stalk": "stalks", "dash": "dashes", "handful": "handfuls", "sheet": "sheets",
    "serving": "servings",
}

# Units shown as fractions (1 1/2 cups). Metric units are shown as decimals (250 g).
METRIC = {"ml", "l", "g", "kg"}
FRACTIONS = [Fraction(n, d) for n, d in
             [(0, 1), (1, 8), (1, 4), (1, 3), (3, 8), (1, 2), (5, 8), (2, 3), (3, 4), (7, 8), (1, 1)]]


def normalize_unit(unit: Optional[str]) -> Optional[str]:
    """'Tablespoons' -> 'tbsp'. Unknown units are lowercased and kept. Blank -> None."""
    if unit is None:
        return None
    cleaned = " ".join(unit.lower().split())
    if not cleaned:
        return None
    return ALIASES.get(cleaned, cleaned)


def _table(unit: str) -> Optional[dict]:
    if unit in VOLUME_ML:
        return VOLUME_ML
    if unit in WEIGHT_G:
        return WEIGHT_G
    return None


def convert(quantity: float, from_unit: Optional[str], to_unit: Optional[str]) -> Optional[float]:
    """Convert between units of the same kind. None if they can't be compared.

    No unit counts as "each": "2 eggs" and "2 each eggs" are the same amount.
    """
    from_unit = normalize_unit(from_unit) or "each"
    to_unit = normalize_unit(to_unit) or "each"
    if from_unit == to_unit:
        return quantity
    table = _table(from_unit)
    if table is None or to_unit not in table:
        return None
    return quantity * table[from_unit] / table[to_unit]


# Measuring cups come in 1/4, 1/3, 1/2 (and 2/3, 3/4 by eye); 3/8 cup is really 6 tbsp.
CUP_FRACTIONS = [Fraction(n, d) for n, d in [(0, 1), (1, 4), (1, 3), (1, 2), (2, 3), (3, 4), (1, 1)]]


def _is_nice(value: float, unit: str) -> bool:
    """Close to a whole number plus a fraction you can actually measure in that unit."""
    whole = int(value)
    fractions = CUP_FRACTIONS if unit == "cup" else FRACTIONS
    return any(abs(value - whole - float(f)) < 0.01 for f in fractions)


# For tidy(): bigger units first, each with the smallest amount worth using it for.
_LADDERS = {
    "spoons": [("cup", 0.25), ("tbsp", 1.0), ("tsp", 0.0)],
    "weight_us": [("lb", 1.0), ("oz", 0.0)],
    "weight_metric": [("kg", 1.0), ("g", 0.0)],
    "volume_metric": [("l", 1.0), ("ml", 0.0)],
}
_LADDER_FOR = {unit: name for name, steps in _LADDERS.items() for unit, _ in steps}


def tidy(quantity: float, unit: Optional[str]) -> tuple:
    """Pick a friendlier unit after scaling: 6 tsp -> 2 tbsp, 0.125 cup -> 2 tbsp, 24 oz -> 1 1/2 lb.

    Only moves to a unit where the amount is a clean kitchen number. Otherwise keeps it.
    """
    ladder = _LADDERS.get(_LADDER_FOR.get(unit or ""))
    if ladder is None:
        return quantity, unit
    options = [(convert(quantity, unit, u), u, minimum) for u, minimum in ladder]
    for value, u, minimum in options:
        if value >= minimum and _is_nice(value, u):
            return value, u
    # Nothing is clean; at least avoid tiny amounts of a big unit (0.1 cup).
    for value, u, minimum in options:
        if value >= minimum and u == unit:
            return quantity, unit
    for value, u, minimum in options:
        if value >= minimum:
            return value, u
    return quantity, unit


def format_quantity(quantity: float, unit: Optional[str] = None) -> str:
    """1.5 -> '1 1/2', 0.333 -> '1/3', 2 -> '2'. Metric: 250.0 g -> '250', 1.25 kg -> '1.25'."""
    if unit in METRIC:
        if quantity >= 10:
            return str(round(quantity))
        return f"{round(quantity, 2):g}"
    if quantity < 0.125:
        return f"{round(quantity, 2):g}"  # smaller than any kitchen fraction
    whole = int(quantity)
    rest = min(FRACTIONS, key=lambda f: abs(quantity - whole - float(f)))
    if rest == 1:
        whole, rest = whole + 1, Fraction(0)
    if rest == 0:
        return str(whole)
    return f"{whole} {rest}" if whole else str(rest)


def unit_label(unit: Optional[str], quantity: float) -> str:
    """'cup' -> 'cups' for more than one. 'each' isn't shown at all ('2 eggs', not '2 each eggs')."""
    if unit is None or unit == "each":
        return ""
    if quantity > 1:
        return PLURALS.get(unit, unit)
    return unit


def format_amount(quantity: Optional[float], unit: Optional[str]) -> str:
    """'1 1/2 cups', '3 cloves', '2' (for 2 eggs), or '' when there's no quantity."""
    if quantity is None:
        return ""
    return " ".join(part for part in (format_quantity(quantity, unit), unit_label(unit, quantity)) if part)


def describe_amount(quantity: Optional[float], unit: Optional[str], name: str) -> str:
    """Amount for a sentence: '1 1/2 cups', '6 eggs' (counted things get their name), or 'some'."""
    if quantity is None:
        return "some"
    amount = format_amount(quantity, unit)
    if (unit or "each") == "each":
        return f"{amount} {pluralize_name(name, quantity, unit)}"
    return amount


def pluralize_name(name: str, quantity: Optional[float], unit: Optional[str]) -> str:
    """'egg' -> 'eggs' when counting more than one ('2 eggs', but '2 cups rice')."""
    if quantity is None or quantity <= 1 or (unit or "each") != "each":
        return name
    words = name.split(" ")
    last = words[-1]
    if last.endswith("s"):
        return name
    if last.endswith(("x", "ch", "sh")) or last in {"tomato", "potato"}:
        last += "es"
    elif last.endswith("y") and last[-2:-1] not in "aeiou":
        last = last[:-1] + "ies"
    else:
        last += "s"
    return " ".join(words[:-1] + [last])
