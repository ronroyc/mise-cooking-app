"""Cooking history routes.

POST   /api/recipes/{id}/cooked   log that you cooked it (optionally subtract from inventory)
GET    /api/history               everything cooked, newest first (?recipe_id= for one recipe)
PATCH  /api/history/{id}          rate it, or change the notes or date
DELETE /api/history/{id}          remove an entry (doesn't put anything back in the inventory)
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.recipes import get_recipe_or_404, scaled_recipe
from app.database.db import get_db
from app.models import CookingLog
from app.schemas.history import CookedCreate, CookedResult, CookingLogOut, CookingLogUpdate
from app.services import history as history_service

router = APIRouter(tags=["history"])


def get_log_or_404(db: Session, log_id: int) -> CookingLog:
    log = history_service.get_log(db, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="History entry not found")
    return log


@router.post("/recipes/{recipe_id}/cooked", response_model=CookedResult, status_code=201)
def log_cooked(recipe_id: int, data: CookedCreate, db: Session = Depends(get_db)):
    recipe = get_recipe_or_404(db, recipe_id)
    scaled = scaled_recipe(db, recipe_id, data.servings)
    log, changes = history_service.log_cooked(
        db, recipe, scaled, data.cooked_on or date.today(), data.rating, data.notes, data.update_inventory,
        data.leftover_servings,
    )
    return CookedResult(log=log, inventory_changes=changes)


@router.get("/history", response_model=list[CookingLogOut])
def list_history(recipe_id: Optional[int] = None, db: Session = Depends(get_db)):
    return history_service.list_logs(db, recipe_id)


@router.patch("/history/{log_id}", response_model=CookingLogOut)
def update_log(log_id: int, data: CookingLogUpdate, db: Session = Depends(get_db)):
    log = get_log_or_404(db, log_id)
    return history_service.update_log(db, log, data.model_dump(exclude_unset=True))


@router.delete("/history/{log_id}", status_code=204)
def delete_log(log_id: int, db: Session = Depends(get_db)):
    history_service.delete_log(db, get_log_or_404(db, log_id))
