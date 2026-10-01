"""Meal prep: plan several recipes at once.

Given the recipes you're making this week (each at its own servings), Slice'd:

1. adds up what they need together, per ingredient ("2 cups rice" + "1 cup rice" = 3 cups),
2. compares that total with the inventory once, so two recipes can't both count the
   same 1 1/2 cups of rice you have: together they need 3, so you buy 1 1/2,
3. lists what several recipes share as "prep together" work: "Cook 3 cups rice once".

No cost, budget, or nutrition: Slice'd has no prices or nutrition data, and making up
numbers would be worse than leaving them out. Optional ingredients are left out,
like everywhere else ("add missing to grocery list" skips them too).
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.inventory import expiration_status
from app.schemas.recipe import RecipeOut
from app.services import grocery as grocery_service
from app.services import matching, units
from app.services.names import match_key

# Things you'd cook in one batch rather than chop: "Cook 3 cups rice once".
COOK_AHEAD = {"rice", "brown rice", "jasmine rice", "basmati rice", "quinoa", "pasta", "noodle", "lentil",
              "farro", "couscous", "barley", "potato", "sweet potato", "chickpea", "black bean", "bean"}

# A word in a preparation note, as an instruction: "finely minced" -> "Mince".
PREP_VERBS = {
    "minced": "Mince", "diced": "Dice", "chopped": "Chop", "sliced": "Slice", "grated": "Grate",
    "shredded": "Shred", "julienned": "Cut", "peeled": "Peel", "cubed": "Cube", "crushed": "Crush",
    "cooked": "Cook", "juiced": "Juice", "zested": "Zest", "torn": "Tear", "cut": "Cut",
    "trimmed": "Trim", "halved": "Halve",
}


@dataclass
class Need:
    name: str
    parts: list = field(default_factory=list)     # [[quantity, unit]], one per unit that won't convert
    unmeasured: bool = False                      # some recipe says "to taste" or gives no amount
    recipes: list = field(default_factory=list)   # titles, in order
    notes: list = field(default_factory=list)     # preparation notes ("minced")

    def add(self, quantity: Optional[float], unit: Optional[str]) -> None:
        if quantity is None:
            self.unmeasured = True
            return
        for part in self.parts:
            extra = units.convert(quantity, unit, part[1])
            if extra is not None:
                part[0] += extra
                return
        self.parts.append([quantity, unit])


def _amount_text(parts: list, name: str, unmeasured: bool) -> str:
    """'3 cups', '2 cups + 3 cloves', or 'some'."""
    texts = [units.describe_amount(*units.tidy(round(q, 4), u), name) for q, u in parts if q > 0]
    if not texts:
        return "some"
    return " + ".join(texts) + (" (plus some to taste)" if unmeasured else "")


def combine(recipes: list) -> dict:
    """match key -> Need, for every required ingredient of every recipe."""
    needs = {}
    for recipe in recipes:
        for item in recipe.ingredients:
            if item.optional:
                continue
            key = match_key(item.name)
            need = needs.setdefault(key, Need(name=item.name))
            need.add(item.quantity, item.unit)
            if recipe.title not in need.recipes:
                need.recipes.append(recipe.title)
            if item.preparation_note and item.preparation_note not in need.notes:
                need.notes.append(item.preparation_note)
    return needs


def _to_buy(key: str, need: Need, inventory: dict, today: date):
    """(parts still to buy, sentence about what you have) for one combined need, or None if covered."""
    item = inventory.get(key)
    usable = item is not None and expiration_status(item.expiration_date, today) != "expired"
    if not usable:
        if key in matching.STAPLES:
            return None
        if not need.parts:
            return [], None  # buy "some"
        return [list(part) for part in need.parts], ("Yours is past its date." if item is not None else None)
    if item.quantity is None or not need.parts:
        return None  # you have some, and amounts can't be compared: trust the cook
    left = item.quantity
    missing = []
    for quantity, unit in need.parts:
        have = units.convert(left, item.unit, unit)
        if have is None:
            continue  # 2 lb in the kitchen, recipes want cups: can't tell, so it counts as covered
        short = quantity - have
        if short > quantity * matching.TOLERANCE:
            missing.append([short, unit])
            left = 0
        else:
            left = units.convert(have - quantity, unit, item.unit) or 0
    if not missing:
        return None
    you_have = units.describe_amount(*units.tidy(item.quantity, item.unit), item.name)
    return missing, f"You have {you_have}; together they need {_amount_text(need.parts, need.name, False)}."


def _amount_with_name(parts: list, name: str) -> str:
    """'3 cups rice', '6 cloves garlic', '4 eggs', or just 'green onion' when unmeasured."""
    texts = []
    for quantity, unit in parts:
        quantity, unit = units.tidy(round(quantity, 4), unit)
        text = units.describe_amount(quantity, unit, name)  # counted things include the name: "4 eggs"
        if (unit or "each") != "each":
            text += f" {name}"
        texts.append(text)
    return " + ".join(texts) or name


def _prep_verb(key: str, need: Need) -> Optional[str]:
    """"Cook" for batch-cooked things, "Mince" for "minced"..., or None when there's
    nothing to do ahead (soy sauce, oil, eggs: you just measure them)."""
    if key in COOK_AHEAD:
        return "Cook"
    verbs = set()
    for note in need.notes:
        found = next((PREP_VERBS[w] for w in note.lower().replace(",", " ").split() if w in PREP_VERBS), None)
        if found:
            verbs.add(found)
    if not verbs:
        return None
    # Recipes that cut it differently (minced here, sliced there): "Prep", and the notes say how.
    return verbs.pop() if len(verbs) == 1 else "Prep"


def _prep_step(key: str, need: Need, verb: str) -> dict:
    amount = _amount_text(need.parts, need.name, need.unmeasured)
    what = _amount_with_name(need.parts, need.name)
    return {
        "name": need.name,
        "instruction": f"{verb} {what} once",
        "amount_text": amount,
        "recipes": need.recipes,
        "notes": need.notes,
    }


def plan(db: Session, recipes: list, today: Optional[date] = None) -> dict:
    today = today or date.today()
    needs = combine(recipes)
    inventory = matching.inventory_by_key(db)

    shopping, covered = [], []
    for key, need in needs.items():
        result = _to_buy(key, need, inventory, today)
        if result is None:
            covered.append(need.name)
            continue
        parts, reason = result
        shopping.append({
            "name": need.name,
            "parts": [{"quantity": round(q, 4), "unit": u} for q, u in parts],
            "amount_text": _amount_text(parts, need.name, not parts),
            "recipes": need.recipes,
            "reason": reason,
        })

    shared = [(key, need, _prep_verb(key, need)) for key, need in needs.items()
              if len(need.recipes) >= 2 and key not in matching.STAPLES]
    shared = sorted((s for s in shared if s[2]), key=lambda s: (-len(s[1].recipes), s[1].name))
    return {
        "recipes": [{"id": r.id, "title": r.title, "servings": r.servings} for r in recipes],
        "total_servings": sum(r.servings for r in recipes),
        "prep_together": [_prep_step(key, need, verb) for key, need, verb in shared],
        "shopping": sorted(shopping, key=lambda s: s["name"]),
        "covered": sorted(covered),
    }


def add_to_grocery(db: Session, recipes: list, today: Optional[date] = None) -> list:
    """Put the plan's shopping list on the grocery list. Returns the rows added or updated."""
    rows = []
    for entry in plan(db, recipes, today)["shopping"]:
        first, *others = entry["recipes"]
        parts = entry["parts"] or [{"quantity": None, "unit": None}]
        for part in parts:
            row = grocery_service.add_item(db, entry["name"], part["quantity"], part["unit"], first, commit=False)
            for title in others:
                grocery_service._add_recipe_title(row, title)
            if row not in rows:
                rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows
