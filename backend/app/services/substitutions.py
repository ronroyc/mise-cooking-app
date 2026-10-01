"""Classic ingredient swaps, written by hand. No AI, no cost, works without a key.

For each ingredient a recipe needs but the kitchen doesn't have, Mise looks here
for swaps and says which ones the kitchen does have ("Parmesan: use your pecorino,
same amount"). A swap never changes the recipe or its corner color: it's advice,
and the cook decides. Anything not in this table can go to the AI assistant
(substitute_ai.py), when a key is set up.

Keys and ingredient names are compared with match_key(), so "scallions" finds
the "green onion" entry and "Pecorino Romano" is not the same as "pecorino".
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.models.inventory import expiration_status
from app.services.names import match_key


@dataclass(frozen=True)
class Swap:
    uses: tuple      # ingredient names, all needed: ("milk", "lemon juice")
    amount: str      # how much, relative to what the recipe asks for
    note: str        # what changes, in a few words


def _swap(uses, amount, note):
    return Swap(tuple(uses) if isinstance(uses, (list, tuple)) else (uses,), amount, note)


SWAPS = {
    # Dairy
    "buttermilk": [
        _swap(["milk", "lemon juice"], "1 cup milk + 1 tbsp lemon juice per cup; rest 5 minutes", "Tangy like buttermilk."),
        _swap(["milk", "white vinegar"], "1 cup milk + 1 tbsp vinegar per cup; rest 5 minutes", "Tangy like buttermilk."),
        _swap(["plain yogurt", "milk"], "3/4 cup yogurt + 1/4 cup milk per cup", "Thick and tangy."),
    ],
    "sour cream": [
        _swap("greek yogurt", "Same amount", "A little tangier and less rich."),
        _swap("plain yogurt", "Same amount", "Thinner and tangier."),
    ],
    "greek yogurt": [_swap("sour cream", "Same amount", "Richer, less tangy.")],
    "plain yogurt": [_swap("greek yogurt", "Same amount, thinned with a splash of milk", "Nearly the same.")],
    "heavy cream": [
        _swap(["milk", "butter"], "3/4 cup milk + 1/4 cup melted butter per cup", "Works in sauces and baking; won't whip."),
    ],
    "milk": [
        _swap("oat milk", "Same amount (unsweetened)", "Slightly sweet; fine in most cooking."),
        _swap("almond milk", "Same amount (unsweetened)", "Thinner and nuttier."),
        _swap("soy milk", "Same amount (unsweetened)", "Closest to dairy milk in baking."),
    ],
    "butter": [
        _swap("olive oil", "3/4 of the amount; for cooking, not baking", "Fruitier, no browned-butter flavor."),
        _swap("vegetable oil", "3/4 of the amount; for cooking, not baking", "Neutral flavor."),
    ],
    "parmesan": [_swap("pecorino", "Same amount", "Also hard, aged, and salty; a little sharper.")],
    "parmesan cheese": [_swap("pecorino", "Same amount", "Also hard, aged, and salty; a little sharper.")],
    "pecorino": [_swap("parmesan", "Same amount", "Milder and nuttier.")],
    "cheddar": [_swap("monterey jack", "Same amount", "Milder; melts well.")],
    "cheddar cheese": [_swap("monterey jack", "Same amount", "Milder; melts well.")],
    "mozzarella": [_swap("provolone", "Same amount", "Sharper; melts well.")],

    # Sour, sweet, salty
    "lemon juice": [
        _swap("lime juice", "Same amount", "Slightly more floral."),
        _swap("white vinegar", "Half the amount", "Sour without the citrus flavor."),
    ],
    "lime juice": [_swap("lemon juice", "Same amount", "Slightly less floral.")],
    "rice vinegar": [
        _swap("apple cider vinegar", "Same amount", "Fruitier and a bit stronger."),
        _swap("white wine vinegar", "Same amount", "A bit sharper."),
    ],
    "brown sugar": [
        _swap(["sugar", "molasses"], "1 cup sugar + 1 tbsp molasses per cup", "The same thing, made at home."),
        _swap("sugar", "Same amount", "Less caramel flavor; baked goods come out a little crisper."),
    ],
    "honey": [_swap("maple syrup", "Same amount", "Thinner, with a maple taste.")],
    "maple syrup": [_swap("honey", "Same amount", "Thicker and more floral.")],
    "soy sauce": [
        _swap("tamari", "Same amount", "Nearly the same, usually gluten-free."),
        _swap("coconut aminos", "Same amount", "Sweeter and much less salty."),
    ],
    "tamari": [_swap("soy sauce", "Same amount", "Nearly the same; contains wheat.")],
    "fish sauce": [_swap("soy sauce", "Same amount", "Salty and savory, without the fishy depth.")],
    "oyster sauce": [_swap("hoisin sauce", "Same amount", "Sweeter.")],

    # Wine and cooking liquids
    "mirin": [
        _swap(["sake", "sugar"], "1 tbsp sake + 1 tsp sugar per tbsp", "Close to mirin."),
        _swap("dry sherry", "Same amount, plus a pinch of sugar", "Nutty rather than sweet."),
    ],
    "sake": [
        _swap("dry sherry", "Same amount", "Nuttier."),
        _swap("chinese cooking wine", "Same amount", "Deeper flavor."),
    ],
    "chinese cooking wine": [_swap("dry sherry", "Same amount", "The usual stand-in for Shaoxing wine.")],
    "shaoxing wine": [_swap("dry sherry", "Same amount", "The usual stand-in for Shaoxing wine.")],
    "white wine": [_swap("chicken broth", "Same amount, plus a squeeze of lemon", "Less acidic and fruity.")],
    "chicken broth": [_swap("vegetable broth", "Same amount", "Lighter flavor.")],
    "chicken stock": [_swap("vegetable broth", "Same amount", "Lighter flavor.")],
    "vegetable broth": [_swap("chicken broth", "Same amount", "No longer vegetarian.")],
    "beef broth": [_swap("chicken broth", "Same amount", "Lighter flavor.")],
    "dashi": [_swap("chicken broth", "Same amount, half broth and half water", "Loses the smoky fish flavor.")],

    # Onions, garlic, herbs, spice
    "shallot": [
        _swap("red onion", "Same amount", "Sharper; cook it a little longer."),
        _swap("onion", "Same amount", "Sharper and less sweet."),
    ],
    "onion": [_swap("shallot", "Same amount", "Milder and sweeter.")],
    "green onion": [_swap("chives", "Same amount", "Milder; add at the end.")],
    "garlic": [_swap("garlic powder", "1/8 tsp per clove", "Less sharp; add it with the liquids.")],
    "ginger": [_swap("ground ginger", "1/4 tsp per tbsp of fresh", "Less bright and zingy.")],
    "cilantro": [_swap("parsley", "Same amount", "Loses cilantro's citrusy taste.")],
    "parsley": [_swap("cilantro", "Same amount", "Stronger, citrusy taste.")],
    "red pepper flake": [_swap("cayenne pepper", "A pinch per 1/2 tsp", "Hotter, so start small.")],

    # Baking and thickening
    "baking powder": [
        _swap(["baking soda", "cream of tartar"], "1/4 tsp soda + 1/2 tsp cream of tartar per tsp", "The same leavening."),
    ],
    "cornstarch": [_swap("all purpose flour", "2 tbsp flour per tbsp cornstarch", "For thickening; a little cloudier.")],
    "all purpose flour": [_swap("bread flour", "Same amount", "Chewier; fine for most cooking.")],
    "bread flour": [_swap("all purpose flour", "Same amount", "Softer, less chewy.")],

    # Oils
    "vegetable oil": [_swap("canola oil", "Same amount", "The same for cooking.")],
    "canola oil": [_swap("vegetable oil", "Same amount", "The same for cooking.")],
    "olive oil": [_swap("vegetable oil", "Same amount", "Neutral flavor.")],

    # Proteins, vegetables, grains
    "ground beef": [
        _swap("ground pork", "Same amount", "Richer."),
        _swap("ground turkey", "Same amount", "Leaner; add a little oil."),
    ],
    "ground pork": [_swap("ground beef", "Same amount", "Beefier, a bit leaner.")],
    "ground turkey": [_swap("ground chicken", "Same amount", "Nearly the same.")],
    "chicken thigh": [_swap("chicken breast", "Same amount", "Leaner; cook it a little less so it stays juicy.")],
    "chicken breast": [_swap("chicken thigh", "Same amount", "Juicier; cook a few minutes longer.")],
    "spinach": [_swap("kale", "Same amount", "Tougher; cook it a few minutes longer.")],
    "spaghetti": [
        _swap("linguine", "Same amount", "Flatter, holds sauce the same."),
        _swap("fettuccine", "Same amount", "Wider; best with creamy sauces."),
    ],
    "penne": [
        _swap("rigatoni", "Same amount", "Bigger tubes."),
        _swap("ziti", "Same amount", "Smooth, straight-cut tubes."),
    ],
    "jasmine rice": [_swap("basmati rice", "Same amount", "Drier and more separate grains.")],
    "basmati rice": [_swap("jasmine rice", "Same amount", "Softer and a little sticky.")],
}

# Look up by match key, so plurals and synonyms find the entry.
_BY_KEY = {match_key(name): swaps for name, swaps in SWAPS.items()}

def swaps_for(name: str) -> list:
    return _BY_KEY.get(match_key(name), [])


def on_hand(name: str, inventory: dict, today: date, staples: frozenset = frozenset()) -> bool:
    """In the inventory and not past its date (or a staple). Amounts aren't checked:
    a swap is a suggestion, and the cook knows whether there's enough."""
    key = match_key(name)
    item = inventory.get(key)
    if item is None:
        return key in staples
    return expiration_status(item.expiration_date, today) != "expired"


def find_swaps(name: str, inventory: dict, today: Optional[date] = None, staples: frozenset = frozenset()) -> list:
    """Swaps for one ingredient, the ones the kitchen can make first:
    [{"uses": [...], "amount": ..., "note": ..., "have": bool}]"""
    today = today or date.today()
    found = [
        {"uses": list(swap.uses), "amount": swap.amount, "note": swap.note,
         "have": all(on_hand(use, inventory, today, staples) for use in swap.uses)}
        for swap in swaps_for(name)
    ]
    return sorted(found, key=lambda s: not s["have"])  # stable: table order within each group
