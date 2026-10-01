"""Recipe photos: saved as files in data/photos, one per recipe.

The database only stores the file name. Each upload gets a new random name
("12-9f3a1c0b.jpg"), so a browser never shows an old cached photo after a change.

The file type is read from the first bytes of the file, not from its name or
the browser's Content-Type, so a renamed text file can't pass as a photo.
"""
import re
import secrets
from typing import Optional

from sqlalchemy.orm import Session

from app import config
from app.models import Recipe

MAX_BYTES = 15 * 1024 * 1024  # an iPhone photo is usually 2 to 8 MB

# HEIC is what iPhones and Macs save by default. Safari shows it; most other browsers don't.
EXTENSIONS = ("jpg", "png", "webp", "heic")
FILENAME_PATTERN = re.compile(r"^\d+-[0-9a-f]{8}\.(?:" + "|".join(EXTENSIONS) + r")$")
MEDIA_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "heic": "image/heic"}
HEIC_BRANDS = {b"heic", b"heix", b"heim", b"heis", b"mif1", b"msf1"}


class InvalidPhotoError(ValueError):
    pass


def detect_extension(data: bytes) -> Optional[str]:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[4:8] == b"ftyp" and data[8:12] in HEIC_BRANDS:
        return "heic"
    return None


def path_for(filename: str):
    """The file on disk, or None for names this app would never create (like "../sliced.db")."""
    if not FILENAME_PATTERN.match(filename):
        return None
    return config.PHOTOS_DIR / filename


def delete_file(filename: Optional[str]) -> None:
    path = path_for(filename) if filename else None
    if path is not None:
        path.unlink(missing_ok=True)


def save_photo(db: Session, recipe: Recipe, data: bytes) -> Recipe:
    """Store a new photo for the recipe, replacing the old one."""
    if not data:
        raise InvalidPhotoError("The photo is empty.")
    if len(data) > MAX_BYTES:
        raise InvalidPhotoError("The photo is too big. The limit is 15 MB.")
    extension = detect_extension(data)
    if extension is None:
        raise InvalidPhotoError("That isn't a photo Slice'd can use. Use a JPEG, PNG, WebP, or HEIC image.")

    config.PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{recipe.id}-{secrets.token_hex(4)}.{extension}"
    (config.PHOTOS_DIR / filename).write_bytes(data)

    old = recipe.photo_filename
    recipe.photo_filename = filename
    db.commit()
    delete_file(old)  # only after the database points at the new file
    return recipe


def remove_photo(db: Session, recipe: Recipe) -> Recipe:
    old = recipe.photo_filename
    recipe.photo_filename = None
    db.commit()
    delete_file(old)
    return recipe
