"""Deterministic ingredient-name matching: "Eggs" and "egg", "scallions" and "green onion".

Stored names stay the way the user wrote them (lowercased). Instead, every name gets a
*match key*, and two names mean the same ingredient when their keys are equal:

    "Large Eggs"         -> "egg"
    "scallions"          -> "green onion"
    "All-Purpose Flour"  -> "all purpose flour"

Keys are for comparing only. They're never shown to the user, so they don't need to
be pretty, just consistent: "oats" -> "oat" is odd English but still matches "oat".
"""
import re

# Words at the start that describe the ingredient without changing what it is.
# ("dried" and "ground" are left alone: ground cumin isn't cumin seeds.)
DESCRIPTORS = {"fresh", "freshly", "large", "small", "medium", "jumbo", "organic"}

# Spelling variants, fixed word by word before anything else.
SPELLINGS = {"chilli": "chili", "chile": "chili", "chilies": "chili", "chiles": "chili",
             "chillies": "chili", "yoghurt": "yogurt"}

# Plurals the simple rules below would get wrong.
IRREGULAR_PLURALS = {
    "leaves": "leaf", "halves": "half", "loaves": "loaf",
    "cookies": "cookie", "brownies": "brownie", "pies": "pie", "veggies": "veggie",
}

# Words that end in "s" but aren't plural.
NOT_PLURAL = {"molasses", "hummus", "asparagus", "couscous", "citrus", "swiss", "grits", "jus", "harissa"}

# Different names for the same thing, after the steps above (so singular, no hyphens).
SYNONYMS = {
    "scallion": "green onion",
    "spring onion": "green onion",
    "garbanzo bean": "chickpea",
    "aubergine": "eggplant",
    "courgette": "zucchini",
    "capsicum": "bell pepper",
    "corn starch": "cornstarch",
    "cornflour": "cornstarch",
    "plain flour": "all purpose flour",
    "ap flour": "all purpose flour",
    "powdered sugar": "confectioners sugar",
    "icing sugar": "confectioners sugar",
    "granulated sugar": "sugar",
    "white sugar": "sugar",
    "kosher salt": "salt",
    "table salt": "salt",
    "ground black pepper": "black pepper",
    "extra virgin olive oil": "olive oil",
    "red chili flake": "red pepper flake",
    "chili flake": "red pepper flake",
}


def singular(word: str) -> str:
    """'tomatoes' -> 'tomato', 'berries' -> 'berry', 'peaches' -> 'peach', 'eggs' -> 'egg'."""
    if word in IRREGULAR_PLURALS:
        return IRREGULAR_PLURALS[word]
    if len(word) <= 3 or word in NOT_PLURAL or word.endswith(("ss", "us", "is")):
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith(("ches", "shes", "xes", "zes", "oes", "sses")):
        return word[:-2]
    if word.endswith("s"):
        return word[:-1]
    return word


def match_key(name: str) -> str:
    """The comparison key for an ingredient name. Equal keys = same ingredient."""
    text = name.lower().replace("-", " ")
    text = re.sub(r"[^a-z0-9 ]", "", text)  # "confectioners' sugar" -> "confectioners sugar"
    words = [SPELLINGS.get(w, w) for w in text.split()]
    if words[:2] == ["extra", "large"]:
        words = words[1:]
    while len(words) > 1 and words[0] in DESCRIPTORS:
        words = words[1:]
    if not words:
        return ""
    words[-1] = singular(words[-1])  # the noun is usually last: "cherry tomatoes"
    key = " ".join(words)
    return SYNONYMS.get(key, key)
