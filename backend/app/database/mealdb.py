"""Add TheMealDB's recipes (about 800, free) to a Slice'd database, or take them out again.

Run from the backend/ folder:

    python -m app.database.mealdb              add them, with photos (about 40 MB)
    python -m app.database.mealdb --no-photos  add them without photos (plain colored covers)
    python -m app.database.mealdb --remove     take them out again, except pinned or cooked ones

It uses the same database as the server (DATABASE_URL, data/sliced.db by default) and
the same photos folder (PHOTOS_DIR). Running it again only adds recipes that are new.
Restart isn't needed: the server reads the database on every request.
"""
import argparse

from app import models  # noqa: F401  (registers every table)
from app.database.db import Base, SessionLocal, engine
from app.database.migrate import add_missing_columns
from app.services import mealdb
from app.services.recipe_import import ImportFailed, fetch


def main() -> None:
    parser = argparse.ArgumentParser(description="Add TheMealDB's recipes to Slice'd, or remove them.")
    parser.add_argument("--no-photos", action="store_true", help="don't download photos")
    parser.add_argument("--remove", action="store_true", help="remove TheMealDB recipes (keeps pinned or cooked)")
    args = parser.parse_args()

    # The same setup the server does at startup, in case the server hasn't run since an update.
    Base.metadata.create_all(bind=engine)
    add_missing_columns(engine)

    with SessionLocal() as db:
        if args.remove:
            result = mealdb.remove_imported(db)
            print(f"Removed {result['removed']} recipes. Kept {result['kept']} that are pinned or cooked.")
            return

        print("Reading TheMealDB's catalog...")
        try:
            meals = mealdb.fetch_catalog()
        except ImportFailed as error:
            raise SystemExit(str(error))
        print(f"Found {len(meals)} recipes. Saving the new ones" + ("..." if args.no_photos else " with photos..."))

        def progress(added: int) -> None:
            if added % 50 == 0:
                print(f"  {added} added")

        result = mealdb.save_meals(db, meals, fetch_bytes=None if args.no_photos else fetch, progress=progress)

    print(f"Added {result['added']} recipes ({result['already_there']} were already there).")
    if not args.no_photos:
        print(f"Photos: {result['photos']} saved, {result['photo_failures']} couldn't be downloaded.")
    for reason in result["skipped"]:
        print(f"  Skipped {reason}")


if __name__ == "__main__":
    main()
