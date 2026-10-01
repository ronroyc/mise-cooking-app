"""Tests for the substitution assistant: the hand-written swap table, swaps in
ingredient matches, and the AI suggestions (with a fake client, so no real API
calls, no key, and no cost)."""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.services import ai, substitute_ai
from app.services.substitute_ai import SubstituteIdea, SubstituteSuggestions
from app.services.substitutions import SWAPS, find_swaps, swaps_for


def create_recipe(client, ingredients, title="Test Dish"):
    body = {"title": title, "servings": 2, "prep_time": 5, "cook_time": 10,
            "instructions": "Cook it.\nServe it.", "ingredients": ingredients}
    response = client.post("/api/recipes", json=body)
    assert response.status_code == 201, response.json()
    return response.json()


def stock(client, name, quantity=None, unit=None, **fields):
    response = client.post("/api/inventory", json={"name": name, "quantity": quantity, "unit": unit, **fields})
    assert response.status_code == 201, response.json()
    return response.json()


def fake_item(name, expires=None):
    return SimpleNamespace(name=name, expiration_date=expires)


# ---------- The table ----------

def test_every_swap_is_complete():
    for name, swaps in SWAPS.items():
        assert swaps, name
        for swap in swaps:
            assert swap.uses and swap.amount and swap.note, name
            assert "—" not in swap.note + swap.amount and "–" not in swap.note + swap.amount  # no dashes


def test_lookup_uses_match_keys():
    assert swaps_for("Scallions") == SWAPS["green onion"]  # synonym and plural
    assert swaps_for("Parmesan") == SWAPS["parmesan"]
    assert swaps_for("unicorn tears") == []


def test_swaps_you_can_make_come_first():
    inventory = {"lime juice": fake_item("lime juice")}
    swaps = find_swaps("lemon juice", inventory)
    assert [(s["uses"], s["have"]) for s in swaps] == [(["lime juice"], True), (["white vinegar"], False)]


def test_a_swap_needs_everything_it_uses():
    only_milk = {"milk": fake_item("milk")}
    both = {"milk": fake_item("milk"), "lemon juice": fake_item("lemon juice")}
    assert find_swaps("buttermilk", only_milk)[0]["have"] is False
    assert find_swaps("buttermilk", both)[0] == {
        "uses": ["milk", "lemon juice"], "amount": "1 cup milk + 1 tbsp lemon juice per cup; rest 5 minutes",
        "note": "Tangy like buttermilk.", "have": True}


def test_expired_items_and_staples():
    today = date(2026, 9, 28)
    expired = {"pecorino": fake_item("pecorino", expires=today - timedelta(days=1))}
    assert find_swaps("parmesan", expired, today)[0]["have"] is False
    assert find_swaps("white wine", {}, today, staples=frozenset({"chicken broth"}))[0]["have"] is True


# ---------- Swaps in the ingredient match ----------

def test_match_includes_swaps_for_missing_ingredients(client):
    recipe = create_recipe(client, [
        {"name": "spaghetti", "quantity": 8, "unit": "oz"},
        {"name": "parmesan", "quantity": 0.5, "unit": "cup"},
        {"name": "saffron", "quantity": 1, "unit": "pinch"},
    ])
    stock(client, "spaghetti", 1, "lb")
    stock(client, "pecorino", 4, "oz")

    match = client.get(f"/api/recipes/{recipe['id']}/match").json()
    by_name = {m["name"]: m for m in match["ingredients"]}

    assert by_name["spaghetti"]["swaps"] == []  # you have it: no swaps needed
    assert by_name["parmesan"]["swaps"][0]["uses"] == ["pecorino"]
    assert by_name["parmesan"]["swaps"][0]["have"] is True
    assert by_name["saffron"]["swaps"] == []  # not in the table: that's what the AI is for
    assert (match["have_count"], match["swap_count"], match["color"]) == (1, 1, "red")  # a swap doesn't change the color

    [rec] = client.get("/api/recommendations").json()["recommendations"]
    assert rec["swap_count"] == 1


def test_short_ingredients_get_swaps_too(client):
    recipe = create_recipe(client, [{"name": "lemon juice", "quantity": 3, "unit": "tbsp"}])
    stock(client, "lemon juice", 1, "tbsp")
    stock(client, "lime juice", 0.5, "cup")

    [item] = client.get(f"/api/recipes/{recipe['id']}/match").json()["ingredients"]

    assert item["status"] == "short"
    assert item["swaps"][0]["uses"] == ["lime juice"]


# ---------- The AI service ----------

class FakeClient:
    def __init__(self, result=None, stop_reason="end_turn"):
        self.calls = []
        response = SimpleNamespace(parsed_output=result, stop_reason=stop_reason)

        def parse(**kwargs):
            self.calls.append(kwargs)
            return response

        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=parse))


def idea(substitute, uses=None):
    return SubstituteIdea(substitute=substitute, uses_from_kitchen=uses, amount="Same amount",
                          how_it_changes="A little different.")


def suggestions(*ideas, can_leave_out=False):
    return SubstituteSuggestions(ideas=list(ideas), can_leave_out=can_leave_out, leave_out_note=None)


def sample_recipe(client):
    recipe = create_recipe(client, [
        {"name": "rice", "quantity": 2, "unit": "cup"},
        {"name": "gochujang", "quantity": 2, "unit": "tbsp", "preparation_note": "or to taste"},
    ], title="Kimchi Fried Rice")
    from app.schemas.recipe import RecipeOut
    return RecipeOut.model_validate(recipe)


def test_ai_gets_the_recipe_the_missing_ingredient_and_the_kitchen(client, monkeypatch):
    fake = FakeClient(result=suggestions(idea("sriracha + miso", uses="sriracha"), idea("chili crisp", uses="made up")))
    monkeypatch.setattr(ai, "_client", lambda: fake)

    result = substitute_ai.suggest_substitutes(sample_recipe(client), "gochujang", "2 tbsp", ["miso", "sriracha"])

    call = fake.calls[0]
    assert call["model"] == ai.MODEL
    assert call["output_format"] is SubstituteSuggestions
    assert call["output_config"] == {"effort": "medium"}
    assert call["fallbacks"] == "default"
    content = call["messages"][0]["content"]
    assert "Title: Kimchi Fried Rice" in content
    assert "- 2 tbsp gochujang, or to taste" in content
    assert "<missing>2 tbsp gochujang</missing>" in content
    assert "<kitchen>\nmiso\nsriracha\n</kitchen>" in content
    assert [i.uses_from_kitchen for i in result.ideas] == ["sriracha", None]  # made-up kitchen items are dropped


def test_ai_ideas_are_capped(client, monkeypatch):
    monkeypatch.setattr(ai, "_client", lambda: FakeClient(result=suggestions(*[idea(f"thing {n}") for n in range(7)])))
    result = substitute_ai.suggest_substitutes(sample_recipe(client), "gochujang", "2 tbsp", [])
    assert len(result.ideas) == 4


def test_ai_refusal_is_a_readable_error(client, monkeypatch):
    monkeypatch.setattr(ai, "_client", lambda: FakeClient(result=None, stop_reason="refusal"))
    with pytest.raises(ai.AIError, match="couldn't suggest"):
        substitute_ai.suggest_substitutes(sample_recipe(client), "gochujang", "2 tbsp", [])


# ---------- The endpoints ----------

def test_ai_status(client, monkeypatch):
    monkeypatch.setattr(ai, "is_available", lambda: False)
    assert client.get("/api/ai/status").json() == {"available": False}
    monkeypatch.setattr(ai, "is_available", lambda: True)
    assert client.get("/api/ai/status").json() == {"available": True}


def test_without_a_key_the_endpoint_explains(client, monkeypatch):
    monkeypatch.setattr(ai, "is_available", lambda: False)
    recipe = create_recipe(client, [{"name": "gochujang", "quantity": 2, "unit": "tbsp"}])

    body = client.post(f"/api/recipes/{recipe['id']}/substitutes", json={"ingredient": "gochujang"}).json()

    assert body["ai_available"] is False
    assert body["ideas"] == []
    assert "ANTHROPIC_API_KEY" in body["message"]


def test_endpoint_sends_only_usable_kitchen_items(client, monkeypatch):
    monkeypatch.setattr(ai, "is_available", lambda: True)
    calls = []

    def fake_suggest(recipe, missing, amount, kitchen):
        calls.append((recipe.servings, missing, amount, kitchen))
        return suggestions(idea("sriracha", uses="sriracha"), can_leave_out=True)

    monkeypatch.setattr(substitute_ai, "suggest_substitutes", fake_suggest)
    recipe = create_recipe(client, [{"name": "gochujang", "quantity": 2, "unit": "tbsp"}])
    stock(client, "sriracha")
    stock(client, "old miso", expiration_date=(date.today() - timedelta(days=3)).isoformat())

    body = client.post(f"/api/recipes/{recipe['id']}/substitutes?servings=4", json={"ingredient": "Gochujang"}).json()

    assert calls == [(4, "gochujang", "1/4 cup", ["sriracha"])]  # scaled (4 tbsp); the expired miso isn't offered
    assert body["ai_available"] is True
    assert body["ideas"][0]["uses_from_kitchen"] == "sriracha"
    assert body["can_leave_out"] is True
    assert body["message"] is None


def test_endpoint_turns_ai_errors_into_a_message(client, monkeypatch):
    monkeypatch.setattr(ai, "is_available", lambda: True)

    def failing(*args):
        raise ai.AIError("The AI is busy right now. Try again in a minute.")

    monkeypatch.setattr(substitute_ai, "suggest_substitutes", failing)
    recipe = create_recipe(client, [{"name": "gochujang", "quantity": 2, "unit": "tbsp"}])

    response = client.post(f"/api/recipes/{recipe['id']}/substitutes", json={"ingredient": "gochujang"})

    assert response.status_code == 200
    assert response.json()["ideas"] == []
    assert "busy" in response.json()["message"]


def test_endpoint_rejects_an_ingredient_the_recipe_doesnt_use(client, monkeypatch):
    monkeypatch.setattr(ai, "is_available", lambda: True)
    recipe = create_recipe(client, [{"name": "rice", "quantity": 1, "unit": "cup"}])

    response = client.post(f"/api/recipes/{recipe['id']}/substitutes", json={"ingredient": "caviar"})

    assert response.status_code == 404
    assert client.post("/api/recipes/999/substitutes", json={"ingredient": "rice"}).status_code == 404
