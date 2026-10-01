"""Database connection setup.

- engine:       knows how to talk to the SQLite file
- SessionLocal: creates a new session (a "conversation" with the database)
- Base:         parent class for all table models (added in Milestone 1)
- get_db:       gives each API request its own session, then closes it
"""
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATA_DIR, DATABASE_URL

DATA_DIR.mkdir(exist_ok=True)


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """SQLite ignores foreign keys unless you turn them on for every connection.

    Without this, you could point a recipe_ingredient at a recipe that doesn't exist.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# SQLite normally only allows the thread that opened a connection to use it.
# FastAPI may handle a request on a different thread, so we turn that check off.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: open a session for one request, always close it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
