"""Tests for importing recipes from websites. No real network: fetching is replaced
with a function that returns a saved page."""
import json

import pytest

from app.services import recipe_import
from app.services.recipe_import import (
    find_recipe_data, parse_ingredient_line, parse_ingredients, parse_minutes, parse_servings, parse_steps,
)

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100


def page_with(*blocks, extra=""):
    scripts = "".join(
        f'<script type="application/ld+json">{b if isinstance(b, str) else json.dumps(b)}</script>' for b in blocks
    )
    return f"<html><head><title>Food blog</title>{scripts}</head><body>{extra}Long story about my grandmother.</body></html>"


RECIPE = {
    "@context": "https://schema.org",
    "@type": "Recipe",
    "name": "Garlic Butter Noodles &amp; Herbs",
    "description": "<p>Quick, buttery, and <b>garlicky</b>.</p>",
    "image": [{"@type": "ImageObject", "url": "https://example.com/noodles.jpg"}],
    "recipeYield": ["4", "4 servings"],
    "prepTime": "PT10M",
    "cookTime": "PT15M",
    "recipeCuisine": ["Italian", "American"],
    "recipeIngredient": [
        "8 oz spaghetti",
        "4 tablespoons unsalted butter",
        "4 cloves garlic, minced",
        "Salt and pepper, to taste",
        "1/4 cup chopped parsley (optional)",
    ],
    "recipeInstructions": [
        {"@type": "HowToStep", "text": "Boil the spaghetti."},
        {"@type": "HowToSection", "name": "Sauce", "itemListElement": [
            {"@type": "HowToStep", "text": "Melt the butter &amp; add garlic."},
            {"@type": "HowToStep", "text": "Toss with the noodles."},
        ]},
    ],
}


@pytest.fixture
def fake_site(monkeypatch):
    """pages[url] = what the site returns (str for a page, bytes for an image)."""
    pages = {}

    def fake_fetch(url, max_bytes):
        url = recipe_import.check_url(url)
        if url not in pages:
            raise recipe_import.ImportFailed("Couldn't reach that site. Check the address and your internet connection.")
        body = pages[url]
        return body.encode() if isinstance(body, str) else body

    monkeypatch.setattr(recipe_import, "fetch", fake_fetch)
    return pages


# ---------- Ingredient lines ----------

@pytest.mark.parametrize("line,name,quantity,unit,note", [
    ("2 cups all-purpose flour", "all-purpose flour", 2, "cup", None),
    ("1 1/2 cups milk", "milk", 1.5, "cup", None),
    ("1½ tsp baking powder", "baking powder", 1.5, "tsp", None),
    ("½ cup sugar", "sugar", 0.5, "cup", None),
    ("3 cloves garlic, minced", "garlic", 3, "clove", "minced"),
    ("2 large eggs", "eggs", 2, None, "large"),
    ("1 (14 oz) can crushed tomatoes", "crushed tomatoes", 1, "can", "14 oz"),
    ("2 to 3 tablespoons olive oil", "olive oil", 3, "tbsp", "2 to 3"),
    ("1 T soy sauce", "soy sauce", 1, "tbsp", None),
    ("1 cup of rice", "rice", 1, "cup", None),
    ("200 g chicken thighs (boneless, skinless)", "chicken thighs", 200, "g", "boneless, skinless"),
    ("2 fl oz lime juice", "lime juice", 2, "fl oz", None),
    ("1 tomato", "tomato", 1, None, None),
    ("Kosher salt", "kosher salt", None, None, None),
    ("Fresh basil, for serving", "fresh basil", None, None, "for serving"),
    ("<b>1 lb</b> ground beef", "ground beef", 1, "lb", None),
    # Lines from real recipe sites that broke the first version:
    ("½ onion ((4 oz, 113 g; peeled and sliced))", "onion", 0.5, None, "4 oz, 113 g; peeled and sliced"),
    ("10 oz boneless, skinless chicken thighs", "boneless skinless chicken thighs", 10, "oz", None),
    ("200 g / 6 oz chow mein noodles ((Note 2))", "chow mein noodles", 200, "g", "Note 2"),
    ("200g/6oz chicken breast, thinly sliced", "chicken breast", 200, "g", "thinly sliced"),
    ("1 tbsp sunflower or vegetable oil plus a little extra for frying", "sunflower or vegetable oil", 1, "tbsp",
     "plus a little extra for frying"),
    ("lemon wedges to serve", "lemon wedges", None, None, "to serve"),
    ("4 sprigs mitsuba ((Japanese parsley))", "mitsuba", 4, "sprig", "Japanese parsley"),
    ("1.5 tbsp soy sauce ((sub light soy)", "soy sauce", 1.5, "tbsp", "sub light soy"),
    ("2 tsp sugar, divided", "sugar", 2, "tsp", "divided"),
    ("1½ cups plus 1 Tbsp. all-purpose flour (200 g)", "all-purpose flour", 1.5625, "cup", "200 g"),
    ("½ cup toasted pine nuts", "pine nuts", 0.5, "cup", "toasted"),
    ("¼ cup freshly grated Parmesan cheese", "parmesan cheese", 0.25, "cup", "freshly grated"),
    ("1 (28 oz) can crushed tomatoes", "crushed tomatoes", 1, "can", "28 oz"),  # a product, not a prep
    ("1 lb ground beef", "ground beef", 1, "lb", None),
])
def test_parse_ingredient_line(line, name, quantity, unit, note):
    item = parse_ingredient_line(line)
    assert (item["name"].lower(), item["quantity"], item["unit"], item["preparation_note"]) == (name, quantity, unit, note)


def test_freshly_ground_pepper_is_the_black_pepper_staple():
    from app.services.names import match_key
    assert match_key(parse_ingredient_line("Freshly ground black pepper")["name"]) == "black pepper"


def test_optional_ingredient():
    item = parse_ingredient_line("1/4 cup chopped parsley (optional)")
    assert (item["name"], item["quantity"], item["optional"]) == ("parsley", 0.25, True)
    assert item["preparation_note"] == "chopped"


def test_salt_and_pepper_become_two_staples():
    items, warnings = parse_ingredients(["Salt and pepper, to taste"])
    assert [(i["name"], i["quantity"]) for i in items] == [("salt", None), ("black pepper", None)]
    assert warnings == []


def test_same_ingredient_twice_is_combined():
    items, warnings = parse_ingredients(["1 cup sugar", "2 tbsp sugar", "1 egg", "2 eggs"])
    assert [(i["name"], i["quantity"], i["unit"]) for i in items] == [("sugar", 1.125, "cup"), ("egg", 3, None)]
    assert warnings == []


def test_same_ingredient_that_cant_be_added_gets_a_warning():
    items, warnings = parse_ingredients(["1 cup flour", "100 g flour"])
    assert len(items) == 1
    assert "flour" in warnings[0]


def test_empty_name_is_skipped_with_a_warning():
    items, warnings = parse_ingredients(["2 cups", "1 onion"])
    assert [i["name"] for i in items] == ["onion"]
    assert warnings == ['Skipped "2 cups": couldn\'t find an ingredient name.']


# ---------- Other fields ----------

@pytest.mark.parametrize("value,minutes", [
    ("PT45M", 45), ("PT1H30M", 90), ("P0DT0H20M", 20), ("PT2H", 120), ("PT90S", 2), ("", None), ("soon", None),
    (None, None), ("PT", None),
])
def test_parse_minutes(value, minutes):
    assert parse_minutes(value) == minutes


@pytest.mark.parametrize("value,servings", [
    ("4", 4), (6, 6), (["4", "4 servings"], 4), ("Makes 6 to 8 servings", 6), ("serves a crowd", None), (None, None),
])
def test_parse_servings(value, servings):
    assert parse_servings(value) == servings


def test_parse_steps_from_html_string():
    assert parse_steps("<p>Chop.</p><p>Fry &amp; serve.</p>") == ["Chop.", "Fry & serve."]
    assert parse_steps("Chop.\nFry.") == ["Chop.", "Fry."]


# ---------- Finding the recipe in the page ----------

def test_finds_recipe_inside_graph():
    graph = {"@context": "https://schema.org", "@graph": [{"@type": "WebPage"}, dict(RECIPE, name="In a graph")]}
    assert find_recipe_data(page_with(graph))["name"] == "In a graph"


def test_finds_recipe_with_type_list_and_skips_broken_blocks():
    recipe = dict(RECIPE, **{"@type": ["Recipe", "NewsArticle"]}, name="Listed type")
    assert find_recipe_data(page_with("{ not json", [{"@type": "Organization"}, recipe]))["name"] == "Listed type"


def test_image_choice():
    from app.services.recipe_import import image_url
    assert image_url("https://x.com/a.jpg") == "https://x.com/a.jpg"
    assert image_url(["https://x.com/full.jpg", "https://x.com/500x500.jpg"]) == "https://x.com/full.jpg"
    assert image_url([{"url": "https://x.com/s.jpg", "width": 300}, {"url": "https://x.com/l.jpg", "width": "1200"}]) \
        == "https://x.com/l.jpg"
    assert image_url({"url": "/relative.jpg"}) is None
    assert image_url([]) is None


def test_no_recipe_data():
    assert find_recipe_data(page_with({"@type": "WebPage"})) is None


# ---------- The API ----------

def test_import_makes_a_draft(client, fake_site):
    fake_site["https://example.com/noodles"] = page_with(RECIPE)

    response = client.post("/api/recipes/import", json={"url": "https://example.com/noodles"})

    assert response.status_code == 200, response.json()
    draft = response.json()
    assert draft["title"] == "Garlic Butter Noodles & Herbs"
    assert draft["description"] == "Quick, buttery, and garlicky."
    assert (draft["servings"], draft["prep_time"], draft["cook_time"], draft["cuisine"]) == (4, 10, 15, "Italian")
    assert draft["instructions"] == "Boil the spaghetti.\nMelt the butter & add garlic.\nToss with the noodles."
    assert [i["name"] for i in draft["ingredients"]] == [
        "spaghetti", "unsalted butter", "garlic", "salt", "black pepper", "parsley"]
    assert draft["image_url"] == "https://example.com/noodles.jpg"
    assert draft["source_url"] == "https://example.com/noodles"
    assert draft["warnings"] == []
    assert client.get("/api/recipes").json() == []  # nothing saved yet


def test_draft_can_be_saved_as_is(client, fake_site):
    fake_site["https://example.com/noodles"] = page_with(RECIPE)
    draft = client.post("/api/recipes/import", json={"url": "https://example.com/noodles"}).json()
    body = {k: draft[k] for k in ("title", "description", "cuisine", "servings", "prep_time", "cook_time",
                                  "instructions", "ingredients", "source_url")}

    response = client.post("/api/recipes", json=body)

    assert response.status_code == 201, response.json()
    assert response.json()["source_url"] == "https://example.com/noodles"


def test_total_time_fills_cook_time_and_missing_parts_warn(client, fake_site):
    sparse = {"@type": "Recipe", "name": "Toast", "totalTime": "PT25M", "prepTime": "PT5M",
              "recipeIngredient": ["2 slices bread"]}
    fake_site["https://example.com/toast"] = page_with(sparse)

    draft = client.post("/api/recipes/import", json={"url": "https://example.com/toast"}).json()

    assert (draft["prep_time"], draft["cook_time"], draft["servings"]) == (5, 20, 2)
    assert draft["warnings"] == [
        "The site didn't say how many servings. Mise guessed 2.",
        "The site didn't include the steps. Add them before saving.",
    ]


@pytest.mark.parametrize("url,message", [
    ("example.com/recipe", "starting with https://"),
    ("javascript:alert(1)", "starting with https://"),
    ("https://example.com/none", "doesn't include recipe data"),
    ("https://nowhere.example/", "Couldn't reach that site"),
])
def test_import_errors(client, fake_site, url, message):
    fake_site["https://example.com/none"] = page_with({"@type": "WebPage"})

    response = client.post("/api/recipes/import", json={"url": url})

    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_import_data_from_safari_button(client):
    response = client.post("/api/recipes/import-data", json={"url": "https://example.com/noodles", "recipe": RECIPE})

    assert response.status_code == 200, response.json()
    assert response.json()["title"] == "Garlic Butter Noodles & Herbs"
    assert response.json()["source_url"] == "https://example.com/noodles"


@pytest.mark.parametrize("body", [
    {"url": "https://example.com/x", "recipe": {"@type": "WebPage", "name": "Not a recipe"}},
    {"url": "javascript:alert(1)", "recipe": RECIPE},
])
def test_import_data_rejects_bad_input(client, body):
    assert client.post("/api/recipes/import-data", json=body).status_code == 422


def test_photo_from_url(client, fake_site, photos_dir):
    recipe = client.post("/api/recipes", json={
        "title": "Noodles", "servings": 2, "prep_time": 5, "cook_time": 5, "instructions": "Cook.",
        "ingredients": [{"name": "noodles"}]}).json()
    fake_site["https://example.com/noodles.jpg"] = JPEG
    fake_site["https://example.com/page.html"] = "<html>not a photo</html>"

    saved = client.post(f"/api/recipes/{recipe['id']}/photo/from-url", json={"url": "https://example.com/noodles.jpg"})
    bad = client.post(f"/api/recipes/{recipe['id']}/photo/from-url", json={"url": "https://example.com/page.html"})

    assert saved.status_code == 200
    assert saved.json()["photo_url"].endswith(".jpg")
    assert client.get(saved.json()["photo_url"]).content == JPEG
    assert bad.status_code == 422
    assert client.get(f"/api/recipes/{recipe['id']}").json()["photo_url"] == saved.json()["photo_url"]


def test_source_url_must_be_a_web_address(client):
    response = client.post("/api/recipes", json={
        "title": "Sneaky", "servings": 2, "prep_time": 5, "cook_time": 5, "instructions": "Cook.",
        "ingredients": [{"name": "rice"}], "source_url": "javascript:alert(1)"})
    assert response.status_code == 422
