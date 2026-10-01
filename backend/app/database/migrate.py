"""Add new columns to tables that already exist.

create_all() makes missing tables but never changes existing ones, so a column
added to a model later (like recipes.pinned_at) would be missing from a database
created before it, and every query would fail. This adds those columns.

Only columns that can be empty are added: existing rows get NULL. Anything bigger
(renaming, removing, or a required column) would need a real migration tool.
"""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.database.db import Base


def add_missing_columns(engine: Engine) -> list[str]:
    """Returns the "table.column" names it added."""
    inspector = inspect(engine)
    added = []
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue  # create_all makes it with every column
            existing = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                if not column.nullable:
                    raise RuntimeError(f"Can't add required column {table.name}.{column.name} automatically")
                column_type = column.type.compile(dialect=engine.dialect)
                connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'))
                added.append(f"{table.name}.{column.name}")
    return added
