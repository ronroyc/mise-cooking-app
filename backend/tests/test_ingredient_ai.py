"""Tests for AI ingredient recognition.

No test calls the real Anthropic API: a fake client stands in for it, so the
tests are free, fast, and work without an API key or internet connection.
"""
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.services import ai, ingredient_ai
from app.services.ingredient_ai import IngredientAIError, IngredientIdentification


def identification(**overrides):
    fields = {
        "is_food": True,
        "canonical_name": "chili crunch",
        "matches_existing": None,
        "category": "Sauces & Condiments",
        "typical_location": "pantry",
        "shelf_life_days": 180,
        "description": "Crunchy chili oil with fried garlic and shallots.",
    }
    fields.update(overrides)
    return IngredientIdentification(**fields)


class FakeClient:
    """Stands in for anthropic.Anthropic(). Returns a canned answer or raises an error."""

    def __init__(self, result=None, stop_reason="end_turn", error=None):
        self.calls = []
        response = SimpleNamespace(parsed_output=result, stop_reason=stop_reason)

        def parse(**kwargs):
            self.calls.append(kwargs)
            if error is not None:
                raise error
            return response

        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=parse))


def use_fake_client(monkeypatch, **kwargs):
    fake = FakeClient(**kwargs)
    monkeypatch.setattr(ai, "_client", lambda: fake)
    return fake


def fake_response(status):
    return httpx.Response(status, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))


# ---------- The service (talking to Claude) ----------

def test_identify_sends_the_name_and_known_ingredients(monkeypatch):
    fake = use_fake_client(monkeypatch, result=identification())

    result = ingredient_ai.identify_ingredient("momofuku chili crunch", ["chili powder", "garlic"])

    assert result.canonical_name == "chili crunch"
    call = fake.calls[0]
    assert call["model"] == "claude-opus-5"
    assert call["output_format"] is IngredientIdentification
    assert call["fallbacks"] == "default"
    content = call["messages"][0]["content"]
    assert "<item>momofuku chili crunch</item>" in content
    assert "chili powder\ngarlic" in content


def test_identify_drops_a_match_that_is_not_a_known_ingredient(monkeypatch):
    use_fake_client(monkeypatch, result=identification(matches_existing="made-up thing"))

    result = ingredient_ai.identify_ingredient("chili crunch", ["garlic"])

    assert result.matches_existing is None


def test_identify_keeps_a_real_match(monkeypatch):
    use_fake_client(monkeypatch, result=identification(canonical_name="green onion", matches_existing="green onion"))

    result = ingredient_ai.identify_ingredient("scallions", ["garlic", "green onion"])

    assert result.matches_existing == "green onion"


def test_refusal_becomes_a_readable_error(monkeypatch):
    use_fake_client(monkeypatch, result=None, stop_reason="refusal")

    with pytest.raises(IngredientAIError, match="couldn't identify"):
        ingredient_ai.identify_ingredient("something", [])


@pytest.mark.parametrize(
    "error,message",
    [
        (anthropic.AuthenticationError("bad key", response=fake_response(401), body=None), "rejected"),
        (anthropic.RateLimitError("slow down", response=fake_response(429), body=None), "busy"),
        (anthropic.InternalServerError("oops", response=fake_response(500), body=None), "problem"),
        (anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com")), "internet"),
    ],
    ids=["bad key", "rate limited", "server error", "no connection"],
)
def test_api_errors_become_readable_errors(monkeypatch, error, message):
    use_fake_client(monkeypatch, error=error)

    with pytest.raises(IngredientAIError, match=message):
        ingredient_ai.identify_ingredient("something", [])


# ---------- The endpoint ----------

@pytest.fixture
def ai_on(monkeypatch):
    monkeypatch.setattr(ingredient_ai, "is_available", lambda: True)


def fake_identify(monkeypatch, result=None, error=None):
    calls = []

    def identify(name, known_names):
        calls.append((name, known_names))
        if error:
            raise error
        return result

    monkeypatch.setattr(ingredient_ai, "identify_ingredient", identify)
    return calls


def add_known(client, name, category=None):
    body = {"name": name}
    if category:
        body["category"] = category
    assert client.post("/api/inventory", json=body).status_code == 201


def test_known_ingredient_skips_the_ai(client, ai_on, monkeypatch):
    add_known(client, "garlic", "Produce")
    calls = fake_identify(monkeypatch, result=identification())

    body = client.post("/api/ingredients/identify", json={"name": "  Garlic "}).json()

    assert body["known"] is True
    assert body["category"] == "Produce"
    assert body["suggestion"] is None
    assert calls == []


def test_without_api_key_explains_how_to_turn_it_on(client, monkeypatch):
    monkeypatch.setattr(ingredient_ai, "is_available", lambda: False)
    calls = fake_identify(monkeypatch, result=identification())

    response = client.post("/api/ingredients/identify", json={"name": "chili crunch"})

    assert response.status_code == 200
    body = response.json()
    assert body["ai_available"] is False
    assert "ANTHROPIC_API_KEY" in body["message"]
    assert calls == []


def test_new_ingredient_gets_a_suggestion(client, ai_on, monkeypatch):
    add_known(client, "chili powder")
    calls = fake_identify(monkeypatch, result=identification(canonical_name="Chili  Crunch"))

    body = client.post("/api/ingredients/identify", json={"name": "Momofuku Chili Crunch"}).json()

    assert calls == [("momofuku chili crunch", ["chili powder"])]
    assert body["known"] is False
    suggestion = body["suggestion"]
    assert suggestion["name"] == "chili crunch"  # normalized
    assert suggestion["matches_existing"] is None
    assert suggestion["category"] == "Sauces & Condiments"
    assert suggestion["typical_location"] == "pantry"
    assert suggestion["shelf_life_days"] == 180


def test_synonym_uses_the_existing_name_and_category(client, ai_on, monkeypatch):
    add_known(client, "green onion", "Produce")
    fake_identify(monkeypatch, result=identification(
        canonical_name="negi", matches_existing="green onion", category="Other",
    ))

    suggestion = client.post("/api/ingredients/identify", json={"name": "negi"}).json()["suggestion"]

    assert suggestion["name"] == "green onion"
    assert suggestion["matches_existing"] == "green onion"
    assert suggestion["category"] == "Produce"


@pytest.mark.parametrize("typed", ["eggs", "large eggs", "scallions"])
def test_plurals_and_known_synonyms_skip_the_ai(client, ai_on, monkeypatch, typed):
    add_known(client, "egg", "Dairy")
    add_known(client, "green onion", "Produce")
    calls = fake_identify(monkeypatch, result=identification())

    result = client.post("/api/ingredients/identify", json={"name": typed}).json()

    assert result["known"] is True
    assert result["name"] in {"egg", "green onion"}
    assert calls == []  # matched by the rules, so no paid AI call


def test_non_food_is_flagged(client, ai_on, monkeypatch):
    fake_identify(monkeypatch, result=identification(is_food=False, canonical_name="car keys"))

    suggestion = client.post("/api/ingredients/identify", json={"name": "car keys"}).json()["suggestion"]

    assert suggestion["is_food"] is False


def test_zero_shelf_life_is_treated_as_unknown(client, ai_on, monkeypatch):
    fake_identify(monkeypatch, result=identification(shelf_life_days=0))

    suggestion = client.post("/api/ingredients/identify", json={"name": "chili crunch"}).json()["suggestion"]

    assert suggestion["shelf_life_days"] is None


def test_ai_failure_still_returns_200_with_a_message(client, ai_on, monkeypatch):
    fake_identify(monkeypatch, error=IngredientAIError("Couldn't reach the AI. Check your internet connection."))

    response = client.post("/api/ingredients/identify", json={"name": "muktuk"})

    assert response.status_code == 200
    assert response.json()["suggestion"] is None
    assert "internet" in response.json()["message"]


def test_identify_rejects_empty_name(client):
    assert client.post("/api/ingredients/identify", json={"name": "  "}).status_code == 422


def test_identify_saves_nothing(client, ai_on, monkeypatch):
    fake_identify(monkeypatch, result=identification())

    client.post("/api/ingredients/identify", json={"name": "chili crunch"})

    assert client.get("/api/ingredients").json() == []
    assert client.get("/api/inventory").json() == []


# ---------- Browser caching ----------

@pytest.mark.parametrize("path", ["/", "/inventory.html", "/js/common.js", "/css/style.css"])
def test_frontend_files_are_always_revalidated(client, path):
    """Stops a browser from mixing an old common.js with a new inventory.js."""
    assert client.get(path).headers["cache-control"] == "no-cache"


def test_api_responses_have_no_frontend_cache_header(client):
    assert "cache-control" not in client.get("/api/health").headers
