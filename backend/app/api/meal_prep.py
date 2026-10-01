"""Meal prep routes.

POST /api/meal-prep/plan      combined shopping list and "prep together" steps for several recipes
POST /api/meal-prep/grocery   put that shopping list on the grocery list

Both take {"recipes": [{"id": 3, "servings": 4}, ...]}; servings is optional.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.recipes import scaled_recipe
from app.database.db import get_db
from app.schemas.grocery import GroceryItemOut
from app.services import meal_prep

router = APIRouter(prefix="/meal-prep", tags=["meal prep"])


class PlannedRecipe(BaseModel):
    id: int
    servings: Optional[int] = Field(default=None, gt=0, le=100)


class PlanRequest(BaseModel):
    recipes: list[PlannedRecipe] = Field(min_length=1, max_length=14)


def _recipes(db: Session, data: PlanRequest) -> list:
    ids = [r.id for r in data.recipes]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=422, detail="Each recipe can only be in the plan once.")
    return [scaled_recipe(db, r.id, r.servings) for r in data.recipes]  # 404 for a missing recipe


@router.post("/plan")
def plan(data: PlanRequest, db: Session = Depends(get_db)):
    return meal_prep.plan(db, _recipes(db, data))


@router.post("/grocery", response_model=list[GroceryItemOut])
def add_to_grocery(data: PlanRequest, db: Session = Depends(get_db)):
    return meal_prep.add_to_grocery(db, _recipes(db, data))
