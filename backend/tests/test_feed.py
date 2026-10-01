"""Tests for the recipe feed: corner colors, pins, photos, and adding new columns
to an older database."""
import sqlite3

import pytest
from sqlalchemy import create_engine, inspect

from app.database.migrate import add_missing_columns
from app.services.matching import match_color

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 100
HEIC = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 100


def create_recipe(client, title="Test Dish", ingredients=None):
    body = {
        "title": title, "servings": 2, "prep_time": 5, "cook_time": 10, "instructions": "Cook it.",
        "ingredients": ingredients if ingredients is not None else [{"name": "rice", "quantity": 1, "unit": "cup"}],
    }
    response = client.post("/api/recipes", json=body)
    assert response.status_code == 201, response.json()
    return response.json()


def stock(client, name, quantity=None, unit=None):
    response = client.post("/api/inventory", json={"name": name, "quantity": quantity, "unit": unit})
    assert response.status_code == 201, response.json()
    return response.json()


def upload(client, recipe_id, data, content_type="image/jpeg"):
    return client.put(f"/api/recipes/{recipe_id}/photo", content=data, headers={"Content-Type": content_type})


# ---------- Corner colors ----------

@pytest.mark.parametrize("have,required,color", [
    (4, 4, "green"), (0, 0, "green"),  # nothing required: nothing to buy
    (3, 4, "yellow"), (2, 4, "yellow"), (1, 2, "yellow"),
    (1, 4, "red"), (0, 3, "red"), (2, 5, "red"),
])
def test_match_color(have, required, color):
    assert match_color(have, required) == color


def test_color_follows_the_inventory(client):
    ingredients = [{"name": n, "quantity": 1, "unit": "cup"} for n in ("rice", "beans", "corn", "onion")]
    recipe = create_recipe(client, ingredients=ingredients)

    def color():
        return client.get(f"/api/recipes/{recipe['id']}/match").json()["color"]

    assert color() == "red"
    stock(client, "rice", 2, "cups")
    stock(client, "beans", 2, "cups")
    assert color() == "yellow"
    stock(client, "corn", 2, "cups")
    onion = stock(client, "onion", 0.5, "cup")  # not enough: doesn't count as on hand
    assert color() == "yellow"
    client.patch(f"/api/inventory/{onion['id']}", json={"quantity": 3})
    assert color() == "green"


def test_recommendations_include_color(client):
    create_recipe(client)
    [rec] = client.get("/api/recommendations").json()["recommendations"]
    assert rec["color"] == "red"


# ---------- Pins ----------

def test_pin_and_unpin(client):
    recipe = create_recipe(client)
    assert recipe["pinned"] is False

    assert client.put(f"/api/recipes/{recipe['id']}/pin").json()["pinned"] is True
    assert client.put(f"/api/recipes/{recipe['id']}/pin").json()["pinned"] is True  # pinning twice is fine
    assert client.get(f"/api/recipes/{recipe['id']}").json()["pinned"] is True

    assert client.delete(f"/api/recipes/{recipe['id']}/pin").json()["pinned"] is False
    assert client.get(f"/api/recipes/{recipe['id']}").json()["pinned"] is False


def test_pin_missing_recipe_is_404(client):
    assert client.put("/api/recipes/999/pin").status_code == 404


def test_pinned_filter(client):
    pinned = create_recipe(client, "Pinned Dish")
    create_recipe(client, "Other Dish")
    client.put(f"/api/recipes/{pinned['id']}/pin")

    assert [r["title"] for r in client.get("/api/recipes?pinned=true").json()] == ["Pinned Dish"]
    assert len(client.get("/api/recipes").json()) == 2
    recs = client.get("/api/recommendations?pinned=true").json()["recommendations"]
    assert [r["recipe"]["title"] for r in recs] == ["Pinned Dish"]
    assert recs[0]["recipe"]["pinned"] is True


# ---------- Photos ----------

@pytest.mark.parametrize("data,extension", [(JPEG, "jpg"), (PNG, "png"), (WEBP, "webp"), (HEIC, "heic")])
def test_upload_and_serve_photo(client, photos_dir, data, extension):
    recipe = create_recipe(client)

    response = upload(client, recipe["id"], data)

    assert response.status_code == 200, response.json()
    url = response.json()["photo_url"]
    assert url.startswith(f"/api/photos/{recipe['id']}-") and url.endswith(f".{extension}")
    assert client.get(f"/api/recipes/{recipe['id']}").json()["photo_url"] == url
    served = client.get(url)
    assert served.status_code == 200
    assert served.content == data
    assert served.headers["content-type"].startswith("image/")
    assert len(list(photos_dir.iterdir())) == 1


def test_new_photo_replaces_the_old_file(client, photos_dir):
    recipe = create_recipe(client)
    first = upload(client, recipe["id"], JPEG).json()["photo_url"]
    second = upload(client, recipe["id"], PNG).json()["photo_url"]

    assert first != second
    assert client.get(first).status_code == 404
    assert [p.name for p in photos_dir.iterdir()] == [second.rsplit("/", 1)[1]]


def test_remove_photo(client, photos_dir):
    recipe = create_recipe(client)
    upload(client, recipe["id"], JPEG)

    response = client.delete(f"/api/recipes/{recipe['id']}/photo")

    assert response.status_code == 200
    assert response.json()["photo_url"] is None
    assert list(photos_dir.iterdir()) == []


def test_deleting_recipe_deletes_its_photo(client, photos_dir):
    recipe = create_recipe(client)
    upload(client, recipe["id"], JPEG)

    assert client.delete(f"/api/recipes/{recipe['id']}").status_code == 204
    assert list(photos_dir.iterdir()) == []


@pytest.mark.parametrize("data", [b"", b"hello, not a photo", b"<svg></svg>", b"GIF89a" + b"\x00" * 20])
def test_rejects_non_photos(client, photos_dir, data):
    recipe = create_recipe(client)

    response = upload(client, recipe["id"], data, content_type="image/jpeg")  # the header is ignored

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert client.get(f"/api/recipes/{recipe['id']}").json()["photo_url"] is None
    assert not photos_dir.exists() or list(photos_dir.iterdir()) == []


def test_rejects_huge_photo(client, monkeypatch):
    from app.services import photos
    monkeypatch.setattr(photos, "MAX_BYTES", 50)
    recipe = create_recipe(client)

    response = upload(client, recipe["id"], JPEG)

    assert response.status_code == 413
    assert "too big" in response.json()["detail"]


def test_upload_to_missing_recipe_is_404(client):
    assert upload(client, 999, JPEG).status_code == 404


@pytest.mark.parametrize("name", ["..%2Fsliced.db", "sliced.db", "1-zzzzzzzz.jpg", "1-0123abcd.svg", "1-0123abcd.jpg"])
def test_only_real_photo_files_are_served(client, name):
    assert client.get(f"/api/photos/{name}").status_code == 404


# ---------- Adding new columns to an older database ----------

def test_add_missing_columns_to_old_database(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as old:  # a recipes table from before pins and photos
        old.execute(
            "CREATE TABLE recipes (id INTEGER PRIMARY KEY, title VARCHAR(200), description TEXT, "
            "servings INTEGER, prep_time INTEGER, cook_time INTEGER, cuisine VARCHAR(50), "
            "instructions TEXT, created_at DATETIME, updated_at DATETIME)"
        )
        old.execute("INSERT INTO recipes (title, servings, prep_time, cook_time, instructions) "
                    "VALUES ('Old Dish', 2, 5, 5, 'Cook.')")
    engine = create_engine(f"sqlite:///{path}")

    added = add_missing_columns(engine)

    assert sorted(added) == ["recipes.photo_filename", "recipes.pinned_at", "recipes.source_url"]
    columns = {c["name"] for c in inspect(engine).get_columns("recipes")}
    assert {"pinned_at", "photo_filename"} <= columns
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT title, pinned_at FROM recipes").all() == [("Old Dish", None)]
    assert add_missing_columns(engine) == []  # running it again changes nothing
    engine.dispose()
