"""Build a demo database: sample recipes, a stocked kitchen, pins, and two weeks of
rated meals, so every page has something to show (screenshots, a public demo).

Run from the backend/ folder:

    python -m app.database.demo ../data/demo.db
    DATABASE_URL=sqlite:///../data/demo.db uvicorn app.main:app --port 8001

It always writes a new, separate file and refuses to touch an existing one, so it
can never mix demo data into your own database (data/sliced.db).
"""
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401  (registers every table)
from app.database.db import Base
from app.database.seed import seed_database, seed_inventory
from app.models import Recipe
from app.schemas.recipe import RecipeOut
from app.services import grocery as grocery_service
from app.services import history as history_service
from app.services import recipes as recipe_service

PINNED = ["Chicken Fried Rice", "Oyakodon", "Pasta Pomodoro", "Chana Masala"]

# (days ago, recipe, rating): a cook who loves quick, savory, garlicky food
# and is lukewarm on long, creamy dishes, so taste and "Slice'd knows..." have a story.
MEALS = [
    (13, "Chicken Fried Rice", 5), (12, "Pasta Pomodoro", 4), (11, "Butter Chicken", 3),
    (10, "Oyakodon", 5), (8, "Chicken Fried Rice", 5), (7, "Chicken Tikka Masala", 2),
    (6, "Egg Fried Rice", 4), (5, "Spaghetti Aglio e Olio", 5), (4, "Classic Pancakes", 3),
    (3, "Chicken Fried Rice", 4), (2, "Beef and Broccoli", 4), (1, "Oyakodon", 5),
]

GROCERIES = [("green onion", 1, "bunch"), ("soy sauce", None, None), ("lemon", 2, None)]


def build(path: Path, today: date = None) -> dict:
    if path.exists():
        raise SystemExit(f"{path} already exists. Pick a new file name, or delete it first.")
    today = today or date.today()
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(bind=engine)
    with sessionmaker(bind=engine, autoflush=False)() as db:
        recipes = seed_database(db)
        items = seed_inventory(db, today)
        by_title = {r.title: r for r in db.scalars(select(Recipe))}
        for title in PINNED:
            recipe_service.set_pinned(db, by_title[title], True)
        for days_ago, title, rating in MEALS:
            recipe = by_title[title]
            history_service.log_cooked(
                db, recipe, RecipeOut.model_validate(recipe), today - timedelta(days=days_ago), rating,
                notes=None, update_inventory=False,
            )
        for name, quantity, unit in GROCERIES:
            grocery_service.add_item(db, name, quantity, unit)
    engine.dispose()
    return {"recipes": recipes, "inventory": items, "pinned": len(PINNED), "meals": len(MEALS)}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m app.database.demo PATH_TO_NEW_DEMO.db")
    counts = build(Path(sys.argv[1]))
    print(f"Demo database at {sys.argv[1]}: {counts['recipes']} recipes, {counts['inventory']} kitchen items, "
          f"{counts['pinned']} pinned, {counts['meals']} meals cooked.")
