"""Load the demo recipes and demo inventory from data/.

Run from the backend/ folder:  python -m app.database.seed

Each part only seeds an empty table, so running it twice won't create duplicates.
"""
import json
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import DATA_DIR
from app.database.db import Base, SessionLocal, engine
from app.models import InventoryItem, Recipe
from app.schemas.inventory import InventoryItemCreate
from app.schemas.recipe import RecipeCreate
from app.services import inventory as inventory_service
from app.services import recipes as recipe_service

SEED_FILE = DATA_DIR / "seed_recipes.json"
INVENTORY_SEED_FILE = DATA_DIR / "seed_inventory.json"


def seed_database(db: Session) -> int:
    """Insert the demo recipes. Returns how many were added (0 if recipes already exist)."""
    if db.scalar(select(func.count()).select_from(Recipe)) > 0:
        return 0

    data = json.loads(SEED_FILE.read_text())

    for name, category in data["ingredient_categories"].items():
        recipe_service.get_or_create_ingredient(db, name, category)

    for raw in data["recipes"]:
        # Going through RecipeCreate means seed data gets the same validation as user input.
        recipe_service.create_recipe(db, RecipeCreate(**raw))

    return len(data["recipes"])


def seed_inventory(db: Session, today: Optional[date] = None) -> int:
    """Insert the demo inventory. Returns how many were added (0 if the inventory isn't empty)."""
    if db.scalar(select(func.count()).select_from(InventoryItem)) > 0:
        return 0

    today = today or date.today()
    items = json.loads(INVENTORY_SEED_FILE.read_text())["items"]
    for raw in items:
        raw = dict(raw)
        days = raw.pop("expires_in_days", None)
        if days is not None:
            raw["expiration_date"] = today + timedelta(days=days)
        inventory_service.create_item(db, InventoryItemCreate(**raw))

    return len(items)


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        recipes_added = seed_database(session)
        items_added = seed_inventory(session)
    print(f"Added {recipes_added} demo recipes." if recipes_added else "Database already has recipes. None added.")
    print(f"Added {items_added} demo inventory items." if items_added else "Inventory isn't empty. None added.")
