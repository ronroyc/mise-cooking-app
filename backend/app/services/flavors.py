"""Flavor profiles, worked out with plain code from an ingredient -> flavor table.

Each ingredient Mise knows gets a score from 0 to 1 on eight flavors. A recipe's
flavor comes from its ingredients: for each flavor,

    recipe score = 1 - (1 - a) * (1 - b) * (1 - c) ...

for the scores a, b, c of its ingredients. One strong ingredient makes the recipe
strong in that flavor, several medium ones add up, and it never goes past 1.
Amounts are ignored (a pinch of chili flakes counts like a spoonful), and optional
ingredients are left out. That's rough on purpose: it's simple, explainable
("garlicky because of garlic and green onion"), and needs no AI.

Ingredients not in the table count for nothing, and the recipe says which ones
those are, so the result never pretends to know more than it does.
"""
from app.services.names import match_key

FLAVORS = ("heat", "sweet", "sour", "salty", "umami", "garlicky", "herby", "creamy")

LABELS = {
    "heat": "Heat", "sweet": "Sweet", "sour": "Sour", "salty": "Salty",
    "umami": "Umami", "garlicky": "Garlicky", "herby": "Herby", "creamy": "Creamy",
}


def _f(heat=0, sweet=0, sour=0, salty=0, umami=0, garlicky=0, herby=0, creamy=0):
    return {"heat": heat, "sweet": sweet, "sour": sour, "salty": salty,
            "umami": umami, "garlicky": garlicky, "herby": herby, "creamy": creamy}


TABLE = {
    # Heat
    "chili": _f(heat=0.8), "chili pepper": _f(heat=0.8), "jalapeno": _f(heat=0.7), "serrano": _f(heat=0.8),
    "habanero": _f(heat=0.95), "green chili": _f(heat=0.6), "thai chili": _f(heat=0.9),
    "red pepper flake": _f(heat=0.7), "cayenne pepper": _f(heat=0.8), "chili powder": _f(heat=0.5),
    "gochugaru": _f(heat=0.6), "shichimi togarashi": _f(heat=0.6), "chipotle": _f(heat=0.6),
    "sriracha": _f(heat=0.7, sweet=0.2, garlicky=0.3), "hot sauce": _f(heat=0.7, sour=0.3),
    "gochujang": _f(heat=0.7, sweet=0.3, salty=0.4, umami=0.5),
    "chili crisp": _f(heat=0.7, salty=0.3, umami=0.5, garlicky=0.4), "chili crunch": _f(heat=0.7, umami=0.5, garlicky=0.4),
    "chili oil": _f(heat=0.7), "harissa": _f(heat=0.7, garlicky=0.3), "wasabi": _f(heat=0.7),
    "black pepper": _f(heat=0.15), "ginger": _f(heat=0.35), "ground ginger": _f(heat=0.3),
    "curry paste": _f(heat=0.6, herby=0.3), "green curry paste": _f(heat=0.6, herby=0.5),
    "red curry paste": _f(heat=0.6, herby=0.2), "curry powder": _f(heat=0.3), "garam masala": _f(heat=0.2),
    "smoked paprika": _f(heat=0.15), "paprika": _f(heat=0.1),
    "kimchi": _f(heat=0.4, sour=0.6, salty=0.4, umami=0.4),

    # Sweet
    "sugar": _f(sweet=0.9), "brown sugar": _f(sweet=0.9), "confectioners sugar": _f(sweet=0.9),
    "honey": _f(sweet=0.9), "maple syrup": _f(sweet=0.9), "molasses": _f(sweet=0.8),
    "mirin": _f(sweet=0.6, umami=0.1), "hoisin sauce": _f(sweet=0.7, salty=0.5, umami=0.4, garlicky=0.2),
    "ketchup": _f(sweet=0.6, sour=0.4, salty=0.3), "condensed milk": _f(sweet=0.9, creamy=0.6),
    "chocolate": _f(sweet=0.6, creamy=0.3), "chocolate chip": _f(sweet=0.7, creamy=0.3),
    "vanilla extract": _f(sweet=0.4), "cinnamon": _f(sweet=0.3),
    "carrot": _f(sweet=0.3), "corn": _f(sweet=0.4), "sweet potato": _f(sweet=0.6), "pea": _f(sweet=0.3),
    "bell pepper": _f(sweet=0.25), "red onion": _f(sweet=0.2, garlicky=0.15), "onion": _f(sweet=0.25, garlicky=0.15),
    "pineapple": _f(sweet=0.7, sour=0.4), "apple": _f(sweet=0.6, sour=0.3), "banana": _f(sweet=0.7),
    "orange": _f(sweet=0.6, sour=0.4), "raisin": _f(sweet=0.8), "date": _f(sweet=0.9),
    "balsamic vinegar": _f(sweet=0.5, sour=0.6),
    "tomato": _f(sweet=0.25, sour=0.35, umami=0.3), "crushed tomato": _f(sweet=0.25, sour=0.35, umami=0.3),
    "tomato paste": _f(sweet=0.3, sour=0.2, umami=0.5), "tomato sauce": _f(sweet=0.3, sour=0.3, umami=0.3),

    # Sour
    "lemon": _f(sour=0.8), "lemon juice": _f(sour=0.9), "lemon zest": _f(sour=0.4, herby=0.2),
    "lime": _f(sour=0.8), "lime juice": _f(sour=0.9),
    "vinegar": _f(sour=0.8), "white vinegar": _f(sour=0.8), "rice vinegar": _f(sour=0.7, sweet=0.2),
    "apple cider vinegar": _f(sour=0.8), "white wine vinegar": _f(sour=0.8), "red wine vinegar": _f(sour=0.8),
    "yogurt": _f(sour=0.5, creamy=0.6), "plain yogurt": _f(sour=0.5, creamy=0.6),
    "greek yogurt": _f(sour=0.5, creamy=0.7), "sour cream": _f(sour=0.4, creamy=0.8),
    "buttermilk": _f(sour=0.5, creamy=0.4), "tamarind": _f(sour=0.8, sweet=0.3),
    "pickle": _f(sour=0.7, salty=0.5), "caper": _f(sour=0.5, salty=0.7), "white wine": _f(sour=0.4),
    "tomatillo": _f(sour=0.6),

    # Salty and umami
    "salt": _f(salty=0.3), "kosher salt": _f(salty=0.3),
    "soy sauce": _f(salty=0.9, umami=0.7), "tamari": _f(salty=0.9, umami=0.7), "coconut aminos": _f(salty=0.4, sweet=0.3, umami=0.4),
    "fish sauce": _f(salty=0.9, umami=0.8), "oyster sauce": _f(sweet=0.3, salty=0.7, umami=0.8),
    "miso": _f(salty=0.7, umami=0.8), "doenjang": _f(salty=0.7, umami=0.7),
    "black bean sauce": _f(salty=0.7, umami=0.6, garlicky=0.3), "worcestershire sauce": _f(sweet=0.2, sour=0.3, salty=0.5, umami=0.6),
    "anchovy": _f(salty=0.8, umami=0.9), "olive": _f(salty=0.6), "bacon": _f(salty=0.7, umami=0.6),
    "prosciutto": _f(salty=0.7, umami=0.5), "ham": _f(salty=0.6, umami=0.4), "sausage": _f(heat=0.1, salty=0.5, umami=0.5),
    "parmesan": _f(salty=0.6, umami=0.7, creamy=0.2), "pecorino": _f(salty=0.7, umami=0.6, creamy=0.2),
    "feta": _f(sour=0.2, salty=0.7, creamy=0.3), "cheddar": _f(salty=0.4, umami=0.3, creamy=0.5),
    "cheese": _f(salty=0.4, umami=0.3, creamy=0.5),
    "broth": _f(salty=0.4, umami=0.5), "stock": _f(salty=0.4, umami=0.5), "chicken broth": _f(salty=0.4, umami=0.5),
    "chicken stock": _f(salty=0.4, umami=0.5), "beef broth": _f(salty=0.4, umami=0.6), "vegetable broth": _f(salty=0.3, umami=0.3),
    "bouillon": _f(salty=0.7, umami=0.6), "dashi": _f(salty=0.3, umami=0.8), "nori": _f(salty=0.4, umami=0.6),
    "seaweed": _f(salty=0.4, umami=0.6), "msg": _f(umami=0.9), "nutritional yeast": _f(umami=0.7),
    "mushroom": _f(umami=0.6), "shiitake": _f(umami=0.8), "shiitake mushroom": _f(umami=0.8),
    "beef": _f(umami=0.5), "ground beef": _f(umami=0.5), "steak": _f(umami=0.5), "pork": _f(umami=0.4),
    "ground pork": _f(umami=0.4), "chicken": _f(umami=0.3), "chicken thigh": _f(umami=0.35), "chicken breast": _f(umami=0.3),
    "ground turkey": _f(umami=0.3), "shrimp": _f(sweet=0.2, umami=0.4), "salmon": _f(umami=0.3), "tuna": _f(umami=0.4),
    "egg": _f(umami=0.2, creamy=0.2), "egg yolk": _f(umami=0.2, creamy=0.5), "tofu": _f(umami=0.1, creamy=0.2),
    "sesame oil": _f(umami=0.2), "sake": _f(umami=0.2, sweet=0.1),

    # Garlic and onion family
    "garlic": _f(garlicky=0.95), "garlic powder": _f(garlicky=0.7), "shallot": _f(sweet=0.2, garlicky=0.3),
    "green onion": _f(garlicky=0.3, herby=0.3), "chives": _f(garlicky=0.2, herby=0.5), "leek": _f(sweet=0.2, garlicky=0.2),

    # Herbs
    "basil": _f(herby=0.9), "thai basil": _f(herby=0.9), "parsley": _f(herby=0.8), "cilantro": _f(herby=0.9),
    "mint": _f(herby=0.9), "dill": _f(herby=0.9), "thyme": _f(herby=0.8), "rosemary": _f(herby=0.8),
    "oregano": _f(herby=0.8), "sage": _f(herby=0.8), "tarragon": _f(herby=0.8), "bay leaf": _f(herby=0.5),
    "mitsuba": _f(herby=0.7), "lemongrass": _f(sour=0.3, herby=0.7), "kaffir lime leaf": _f(sour=0.2, herby=0.7),
    "curry leaf": _f(herby=0.7), "italian seasoning": _f(herby=0.7), "herbes de provence": _f(herby=0.8),
    "zaatar": _f(sour=0.3, herby=0.7), "pesto": _f(salty=0.3, garlicky=0.5, herby=0.8, creamy=0.2),
    "arugula": _f(heat=0.1, herby=0.4), "spinach": _f(herby=0.2), "fennel": _f(sweet=0.2, herby=0.4),
    "celery": _f(herby=0.3),

    # Creamy
    "heavy cream": _f(creamy=0.95), "cream": _f(creamy=0.9), "whipping cream": _f(creamy=0.95),
    "half and half": _f(creamy=0.7), "milk": _f(creamy=0.5), "whole milk": _f(creamy=0.5),
    "evaporated milk": _f(sweet=0.2, creamy=0.7), "butter": _f(salty=0.1, creamy=0.7), "unsalted butter": _f(creamy=0.7),
    "ghee": _f(creamy=0.6), "cream cheese": _f(sour=0.2, creamy=0.9), "mascarpone": _f(creamy=0.9),
    "ricotta": _f(creamy=0.8), "mozzarella": _f(salty=0.2, creamy=0.6), "coconut milk": _f(sweet=0.3, creamy=0.8),
    "coconut cream": _f(sweet=0.3, creamy=0.9), "avocado": _f(creamy=0.8), "mayonnaise": _f(sour=0.2, creamy=0.8),
    "peanut butter": _f(sweet=0.3, salty=0.3, umami=0.3, creamy=0.7), "tahini": _f(creamy=0.7), "cashew": _f(creamy=0.5),
}

# Known, but with no strong flavor of their own: they count as zero, not as "unknown".
NEUTRAL = (
    "water", "rice", "flour", "all purpose flour", "bread flour", "cornstarch", "baking powder", "baking soda",
    "yeast", "oat", "quinoa", "pasta", "spaghetti", "penne", "linguine", "fettuccine", "rigatoni", "ziti", "macaroni",
    "noodle", "ramen", "udon", "bread", "tortilla", "potato", "oil", "olive oil", "vegetable oil", "canola oil",
    "peanut oil", "bean", "black bean", "chickpea", "lentil", "cabbage", "broccoli", "zucchini", "cucumber",
    "lettuce", "bean sprout", "eggplant", "cauliflower", "kale", "bok choy", "green bean", "turkey", "cod", "fish",
    # Warm spices: real flavor, but none of these eight.
    "cumin", "coriander", "turmeric", "cardamom", "clove", "nutmeg", "allspice", "star anise", "fenugreek",
)
TABLE.update({name: _f() for name in NEUTRAL if name not in TABLE})

_BY_KEY = {match_key(name): scores for name, scores in TABLE.items()}


def flavor_of_ingredient(name: str):
    """The scores for one ingredient, or None if Mise doesn't know it.

    Tries the whole name, then shorter endings ("unsalted butter" -> "butter",
    "chow mein noodles" -> "noodle"), then shorter beginnings ("salmon fillet" ->
    "salmon", "miso paste" -> "miso").
    """
    words = match_key(name).split()
    for start in range(len(words)):
        found = _BY_KEY.get(" ".join(words[start:]))
        if found is not None:
            return found
    for end in range(len(words) - 1, 0, -1):
        found = _BY_KEY.get(" ".join(words[:end]))
        if found is not None:
            return found
    return None


def level(value: float) -> str:
    if value >= 0.7:
        return "Very high"
    if value >= 0.5:
        return "High"
    if value >= 0.3:
        return "Medium"
    if value >= 0.15:
        return "Low"
    return "Very low"


def recipe_flavor(ingredients) -> dict:
    """Flavor of a recipe from its ingredients (objects with .name and .optional).

    Returns {"values": {flavor: 0-1}, "because": {flavor: [ingredient names, strongest first]},
             "unknown": [names Mise has no flavor data for]}
    """
    remaining = {flavor: 1.0 for flavor in FLAVORS}
    because = {flavor: [] for flavor in FLAVORS}
    unknown = []
    for item in ingredients:
        if item.optional:
            continue
        scores = flavor_of_ingredient(item.name)
        if scores is None:
            unknown.append(item.name)
            continue
        for flavor in FLAVORS:
            remaining[flavor] *= 1 - scores[flavor]
            if scores[flavor] >= 0.2:
                because[flavor].append((scores[flavor], item.name))
    return {
        "values": {flavor: round(1 - remaining[flavor], 3) for flavor in FLAVORS},
        "because": {flavor: [name for _, name in sorted(because[flavor], key=lambda p: -p[0])] for flavor in FLAVORS},
        "unknown": unknown,
    }
