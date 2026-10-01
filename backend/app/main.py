"""Entry point for the Mise backend.

Run from the backend/ folder with:  uvicorn app.main:app --reload
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app import models  # noqa: F401  (registers every table with Base before create_all)
from app.api import (
    grocery, health, history, inventory, meal_prep, photos, profile, recipes, recommendations, substitutes,
)
from app.config import FRONTEND_DIR
from app.database.db import Base, engine
from app.database.migrate import add_missing_columns

logger = logging.getLogger("mise")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts: create any tables that don't exist yet,
    # and add columns that are newer than the database file.
    Base.metadata.create_all(bind=engine)
    for column in add_missing_columns(engine):
        logger.warning("Added column %s to the database", column)
    yield


app = FastAPI(title="Mise", lifespan=lifespan)


# ---------- Error handling ----------
# Every error reaches the browser as {"detail": ...} with a readable message,
# never a stack trace.

def describe_validation_error(error: dict) -> str:
    # error["loc"] looks like ("body", "ingredients", 0, "name"). Turn it into "ingredients 1 name".
    parts = [str(p + 1) if isinstance(p, int) else str(p).replace("_", " ") for p in error["loc"][1:]]
    message = error["msg"].removeprefix("Value error, ")
    return f"{' '.join(parts)}: {message}" if parts else message


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": [describe_validation_error(e) for e in exc.errors()]})


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "A database error occurred. Please try again."})


# ---------- Browser caching ----------

@app.middleware("http")
async def always_check_for_new_frontend_files(request: Request, call_next):
    """Make the browser ask for fresh HTML/CSS/JS on every load.

    Without this, a browser can keep an old common.js while loading a new
    inventory.js, and the page breaks ("Can't find variable: capitalize").
    "no-cache" still lets the browser reuse its copy when the file hasn't
    changed (the server answers 304 Not Modified), so it stays fast.

    Browsers that cached files *before* this header existed never ask again,
    so the HTML also links scripts as "common.js?v=2". A new ?v= is a new URL
    the browser has never seen. Bump it only if a stale copy ever sticks again.
    """
    response = await call_next(request)
    if not request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-cache"
    return response


# ---------- Routes ----------

# All API routes live under /api so they never clash with frontend pages.
app.include_router(health.router, prefix="/api")
app.include_router(recipes.router, prefix="/api")
app.include_router(photos.router, prefix="/api")
app.include_router(substitutes.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")
app.include_router(grocery.router, prefix="/api")
app.include_router(meal_prep.router, prefix="/api")
app.include_router(history.router, prefix="/api")

# Serve the HTML/CSS/JS frontend. This goes last so /api routes are matched first.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
