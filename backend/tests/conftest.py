"""Shared test setup.

Each test gets a fresh, empty SQLite database in a temporary folder,
so tests never touch your real data/mise.db. Photos go to a temporary folder too.

Fixtures:
- db:     a database session, for testing services directly
- client: a fake browser that sends HTTP requests to the app
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import config
from app.database.db import Base, get_db
from app.main import app


@pytest.fixture(autouse=True)
def photos_dir(tmp_path, monkeypatch):
    folder = tmp_path / "photos"
    monkeypatch.setattr(config, "PHOTOS_DIR", folder)
    return folder


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine, autoflush=False)
    engine.dispose()


@pytest.fixture
def db(session_factory):
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def client(session_factory):
    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    # Swap the real database for the test one in every endpoint that uses get_db.
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
