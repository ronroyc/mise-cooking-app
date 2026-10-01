"""Substitution assistant routes.

GET  /api/ai/status                      whether AI features are turned on (an API key is set)
POST /api/recipes/{id}/substitutes       AI ideas for one ingredient the kitchen is missing

The free, hand-written swaps come with every ingredient match instead
(GET /api/recipes/{id}/match), so they need no extra request.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.recipes import ServingsQuery, scaled_recipe
from app.database.db import get_db
from app.models.inventory import expiration_status
from app.services import ai, matching, substitute_ai
from app.services.names import match_key
from app.services.substitute_ai import SubstituteIdea

router = APIRouter(tags=["substitutes"])


class AIStatus(BaseModel):
    available: bool


class SubstituteRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    ingredient: str = Field(min_length=1, max_length=100)


class SubstituteResponse(BaseModel):
    ai_available: bool
    ingredient: str
    ideas: list[SubstituteIdea]
    can_leave_out: Optional[bool]
    leave_out_note: Optional[str]
    message: Optional[str]  # why there are no ideas (no key, or the AI failed)


@router.get("/ai/status", response_model=AIStatus)
def ai_status():
    return AIStatus(available=ai.is_available())


@router.post("/recipes/{recipe_id}/substitutes", response_model=SubstituteResponse)
def suggest_substitutes(
    recipe_id: int, data: SubstituteRequest, servings: Optional[int] = ServingsQuery, db: Session = Depends(get_db),
):
    recipe = scaled_recipe(db, recipe_id, servings)
    wanted = match_key(data.ingredient)
    needed = next((i for i in recipe.ingredients if match_key(i.name) == wanted), None)
    if needed is None:
        raise HTTPException(status_code=404, detail=f"This recipe doesn't use {data.ingredient}.")

    empty = dict(ingredient=needed.name, ideas=[], can_leave_out=None, leave_out_note=None)
    if not ai.is_available():
        return SubstituteResponse(
            ai_available=False, **empty,
            message="AI suggestions are off. Add ANTHROPIC_API_KEY to the .env file to turn them on.",
        )

    # Only what's usable: expired items aren't offered as swaps.
    today = date.today()
    kitchen = sorted(
        item.name for item in matching.inventory_by_key(db).values()
        if expiration_status(item.expiration_date, today) != "expired"
    )
    try:
        result = substitute_ai.suggest_substitutes(recipe, needed.name, needed.amount_text, kitchen)
    except ai.AIError as error:
        return SubstituteResponse(ai_available=True, **empty, message=str(error))
    return SubstituteResponse(
        ai_available=True, ingredient=needed.name, ideas=result.ideas,
        can_leave_out=result.can_leave_out, leave_out_note=result.leave_out_note, message=None,
    )
