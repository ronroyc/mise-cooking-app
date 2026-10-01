"""The demo database builder: a separate file with something on every page."""
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.database.demo import MEALS, PINNED, build
from app.models import CookingLog, Recipe
from app.services import taste


def test_builds_a_full_demo(tmp_path):
    path = tmp_path / "demo.db"

    counts = build(path)

    assert counts["recipes"] > 10 and counts["inventory"] > 5
    engine = create_engine(f"sqlite:///{path}")
    with sessionmaker(bind=engine)() as db:
        assert db.scalar(select(func.count()).select_from(CookingLog)) == len(MEALS)
        assert db.scalar(select(func.count()).select_from(Recipe).where(Recipe.pinned_at.is_not(None))) == len(PINNED)
        assert taste.learn(db) is not None  # enough 4 and 5 star meals for taste to work
    engine.dispose()


def test_refuses_to_overwrite(tmp_path):
    path = tmp_path / "existing.db"
    path.write_text("not empty")
    with pytest.raises(SystemExit):
        build(path)
    assert path.read_text() == "not empty"
