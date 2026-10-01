"""Recipe HTTP routes. Each function: read the request, call the service, return a response.

GET    /api/recipes             list (optional ?search=&cuisine=&max_total_time=&pinned=true)
GET    /api/recipes/cuisines    distinct cuisines, for the filter dropdown
GET    /api/recipes/{id}        one full recipe (optional ?servings= to scale it)
GET    /api/recipes/{id}/match  which ingredients are in the inventory (optional ?servings=)
POST   /api/recipes             create
POST   /api/recipes/import      read a recipe from a website into a draft (not saved)
POST   /api/recipes/import-data the same, from recipe data the "Save to Mise" Safari button read
PATCH  /api/recipes/{id}        update some fields
DELETE /api/recipes/{id}        delete (and its photo)
PUT    /api/recipes/{id}/pin    pin it
DELETE /api/recipes/{id}/pin    unpin it

Photo routes are in api/photos.py.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.models import Recipe
from app.schemas.recipe import (
    RecipeCreate, RecipeImportDataRequest, RecipeImportDraft, RecipeImportRequest, RecipeMatchOut, RecipeOut,
    RecipeSummary, RecipeUpdate,
)
from app.services import matching, photos, recipe_import
from app.services import recipes as recipe_service

router = APIRouter(prefix="/recipes", tags=["recipes"])


def get_recipe_or_404(db: Session, recipe_id: int) -> Recipe:
    recipe = recipe_service.get_recipe(db, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@router.get("", response_model=list[RecipeSummary])
def list_recipes(
    search: Optional[str] = Query(default=None, max_length=100),
    cuisine: Optional[str] = Query(default=None, max_length=50),
    max_total_time: Optional[int] = Query(default=None, ge=0, description="Prep + cook, in minutes"),
    pinned: bool = Query(default=False, description="Only pinned recipes"),
    db: Session = Depends(get_db),
):
    return recipe_service.list_recipes(db, search, cuisine, max_total_time, pinned_only=pinned)


# Declared before /{recipe_id} so "cuisines" isn't treated as a recipe id.
@router.get("/cuisines", response_model=list[str])
def list_cuisines(db: Session = Depends(get_db)):
    return recipe_service.list_cuisines(db)


# Same limit as a recipe's own servings.
ServingsQuery = Query(default=None, gt=0, le=100, description="Scale the recipe to this many servings")


def scaled_recipe(db: Session, recipe_id: int, servings: Optional[int]) -> RecipeOut:
    recipe = RecipeOut.model_validate(get_recipe_or_404(db, recipe_id))
    return recipe_service.scale_recipe(recipe, servings) if servings else recipe


@router.get("/{recipe_id}", response_model=RecipeOut)
def get_recipe(recipe_id: int, servings: Optional[int] = ServingsQuery, db: Session = Depends(get_db)):
    return scaled_recipe(db, recipe_id, servings)


@router.get("/{recipe_id}/match", response_model=RecipeMatchOut)
def match_recipe(recipe_id: int, servings: Optional[int] = ServingsQuery, db: Session = Depends(get_db)):
    return matching.match_recipe(db, scaled_recipe(db, recipe_id, servings))


# A plain def (not async): FastAPI runs it on a worker thread, so waiting on the
# website doesn't hold up other requests.
@router.post("/import", response_model=RecipeImportDraft)
def import_recipe(data: RecipeImportRequest):
    try:
        return recipe_import.import_recipe(data.url)
    except recipe_import.ImportFailed as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.post("/import-data", response_model=RecipeImportDraft)
def import_recipe_data(data: RecipeImportDataRequest):
    try:
        return recipe_import.draft_from_data(data.recipe, data.url)
    except recipe_import.ImportFailed as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.post("", response_model=RecipeOut, status_code=201)
def create_recipe(data: RecipeCreate, db: Session = Depends(get_db)):
    return recipe_service.create_recipe(db, data)


@router.patch("/{recipe_id}", response_model=RecipeOut)
def update_recipe(recipe_id: int, data: RecipeUpdate, db: Session = Depends(get_db)):
    recipe = get_recipe_or_404(db, recipe_id)
    return recipe_service.update_recipe(db, recipe, data)


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int, db: Session = Depends(get_db)):
    recipe = get_recipe_or_404(db, recipe_id)
    photo = recipe.photo_filename
    recipe_service.delete_recipe(db, recipe)
    photos.delete_file(photo)


@router.put("/{recipe_id}/pin", response_model=RecipeSummary)
def pin_recipe(recipe_id: int, db: Session = Depends(get_db)):
    return recipe_service.set_pinned(db, get_recipe_or_404(db, recipe_id), True)


@router.delete("/{recipe_id}/pin", response_model=RecipeSummary)
def unpin_recipe(recipe_id: int, db: Session = Depends(get_db)):
    return recipe_service.set_pinned(db, get_recipe_or_404(db, recipe_id), False)
