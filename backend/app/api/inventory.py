"""Inventory HTTP routes.

GET    /api/inventory          list (optional ?search=&location=&expires_within=)
GET    /api/inventory/{id}     one item
POST   /api/inventory          add an item
PATCH  /api/inventory/{id}     update some fields
DELETE /api/inventory/{id}     remove an item
GET    /api/ingredients        every known ingredient name, for autocomplete
POST   /api/ingredients/identify   ask the AI what a new ingredient is (suggestion only, saves nothing)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.models import InventoryItem
from app.schemas.inventory import (
    IdentifyRequest,
    IdentifyResponse,
    IngredientOut,
    IngredientSuggestion,
    InventoryItemCreate,
    InventoryItemOut,
    InventoryItemUpdate,
    Location,
)
from app.schemas.recipe import normalize_name
from app.services import ingredient_ai
from app.services import inventory as inventory_service
from app.services import recipes as recipe_service

router = APIRouter(tags=["inventory"])


def conflict(error: inventory_service.DuplicateItemError) -> JSONResponse:
    # 409 Conflict: the request is valid, but clashes with what's already stored.
    # existing_id lets the page open the item that's already there ("eggs" -> your "egg").
    return JSONResponse(status_code=409, content={"detail": str(error), "existing_id": error.existing_id})


def get_item_or_404(db: Session, item_id: int) -> InventoryItem:
    item = inventory_service.get_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return item


@router.get("/inventory", response_model=list[InventoryItemOut])
def list_items(
    search: Optional[str] = Query(default=None, max_length=100),
    location: Optional[Location] = None,
    expires_within: Optional[int] = Query(
        default=None, ge=0, le=365, description="Days from today. Includes expired items."
    ),
    db: Session = Depends(get_db),
):
    return inventory_service.list_items(db, search, location, expires_within)


@router.get("/inventory/{item_id}", response_model=InventoryItemOut)
def get_item(item_id: int, db: Session = Depends(get_db)):
    return get_item_or_404(db, item_id)


@router.post("/inventory", response_model=InventoryItemOut, status_code=201)
def create_item(data: InventoryItemCreate, db: Session = Depends(get_db)):
    try:
        return inventory_service.create_item(db, data)
    except inventory_service.DuplicateItemError as error:
        return conflict(error)


@router.patch("/inventory/{item_id}", response_model=InventoryItemOut)
def update_item(item_id: int, data: InventoryItemUpdate, db: Session = Depends(get_db)):
    item = get_item_or_404(db, item_id)
    try:
        return inventory_service.update_item(db, item, data)
    except inventory_service.DuplicateItemError as error:
        return conflict(error)
    except inventory_service.InvalidItemError as error:
        raise HTTPException(status_code=422, detail=[str(error)])


@router.delete("/inventory/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = get_item_or_404(db, item_id)
    inventory_service.delete_item(db, item)


@router.get("/ingredients", response_model=list[IngredientOut])
def list_ingredients(db: Session = Depends(get_db)):
    return inventory_service.list_ingredients(db)


@router.post("/ingredients/identify", response_model=IdentifyResponse)
def identify_ingredient(data: IdentifyRequest, db: Session = Depends(get_db)):
    """Always answers 200: a missing key or AI failure is reported in `message`, not as an error,
    because the user can still add the item without a suggestion."""
    existing = recipe_service.find_ingredient(db, data.name)  # "eggs" finds "egg"
    result = IdentifyResponse(
        name=existing.name if existing else data.name, known=existing is not None,
        category=existing.category if existing else None,
        ai_available=ingredient_ai.is_available(), suggestion=None, message=None,
    )
    if result.known:
        return result  # Slice'd already knows it: no need to ask the AI
    known = {i.name: i.category for i in inventory_service.list_ingredients(db)}
    if not result.ai_available:
        result.message = "AI ingredient recognition is off. Add ANTHROPIC_API_KEY to .env to turn it on."
        return result

    try:
        found = ingredient_ai.identify_ingredient(data.name, sorted(known))
    except ingredient_ai.IngredientAIError as error:
        result.message = str(error)
        return result

    match = found.matches_existing
    if match is not None:
        # Same thing as an ingredient Slice'd already has: save it under that name and category.
        name, category = match, known[match] or found.category
    else:
        name, category = normalize_name(found.canonical_name) or data.name, found.category
    result.suggestion = IngredientSuggestion(
        is_food=found.is_food,
        name=name,
        matches_existing=match,
        category=category,
        typical_location=found.typical_location,
        shelf_life_days=found.shelf_life_days if found.shelf_life_days and found.shelf_life_days > 0 else None,
        description=found.description.strip(),
    )
    return result
