"""Grocery list routes.

GET    /api/grocery                  the list: unchecked first, grouped by store section
GET    /api/grocery/text             what's left to buy as plain text, one item per line (for the Reminders Shortcut)
POST   /api/grocery                  add an item (combines with the same ingredient when it can)
PATCH  /api/grocery/{id}             tick it off, or change the amount
DELETE /api/grocery/{id}             remove it
POST   /api/grocery/from-recipe/{recipe_id}   add what a recipe needs that you don't have (?servings=)
POST   /api/grocery/stock-checked    move checked items into the inventory
DELETE /api/grocery/checked          remove checked items without stocking them
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.recipes import ServingsQuery, scaled_recipe
from app.database.db import get_db
from app.models import GroceryItem
from app.schemas.grocery import (
    AddFromRecipeResult, GroceryItemCreate, GroceryItemOut, GroceryItemUpdate, StockResult,
)
from app.services import grocery as grocery_service

router = APIRouter(prefix="/grocery", tags=["grocery"])


def get_item_or_404(db: Session, item_id: int) -> GroceryItem:
    item = grocery_service.get_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Grocery item not found")
    return item


@router.get("", response_model=list[GroceryItemOut])
def list_items(db: Session = Depends(get_db)):
    return grocery_service.list_items(db)


@router.post("", response_model=GroceryItemOut, status_code=201)
def add_item(data: GroceryItemCreate, db: Session = Depends(get_db)):
    return grocery_service.add_item(db, data.name, data.quantity, data.unit)


# Declared before /{item_id} routes so "checked" isn't read as an id.
@router.get("/text", response_class=PlainTextResponse)
def list_as_text(db: Session = Depends(get_db)):
    return "\n".join(grocery_service.to_buy_lines(db))


@router.post("/stock-checked", response_model=StockResult)
def stock_checked(db: Session = Depends(get_db)):
    return StockResult(messages=grocery_service.stock_checked(db))


@router.delete("/checked", response_model=dict)
def clear_checked(db: Session = Depends(get_db)):
    return {"removed": grocery_service.clear_checked(db)}


@router.post("/from-recipe/{recipe_id}", response_model=AddFromRecipeResult)
def add_from_recipe(recipe_id: int, servings: Optional[int] = ServingsQuery, db: Session = Depends(get_db)):
    recipe = scaled_recipe(db, recipe_id, servings)
    added, skipped = grocery_service.add_from_recipe(db, recipe)
    if added:
        message = f"Added {len(added)} {'item' if len(added) == 1 else 'items'} to your grocery list."
    else:
        message = "You already have everything this recipe needs."
    if skipped:
        message += f" Skipped {skipped} optional {'ingredient' if skipped == 1 else 'ingredients'}."
    return AddFromRecipeResult(added=added, skipped_optional=skipped, message=message)


@router.patch("/{item_id}", response_model=GroceryItemOut)
def update_item(item_id: int, data: GroceryItemUpdate, db: Session = Depends(get_db)):
    item = get_item_or_404(db, item_id)
    try:
        return grocery_service.update_item(db, item, data.model_dump(exclude_unset=True))
    except grocery_service.InvalidItemError as error:
        raise HTTPException(status_code=422, detail=[str(error)])


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    grocery_service.delete_item(db, get_item_or_404(db, item_id))
