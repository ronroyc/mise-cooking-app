"""Profile and flavor routes.

GET /api/profile              stats, flavor profile, most-used ingredients, "Slice'd knows..."
GET /api/recipes/{id}/flavor  one recipe's flavor, and which ingredients it comes from
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.recipes import get_recipe_or_404
from app.database.db import get_db
from app.services import flavors, profile

router = APIRouter(tags=["profile"])


@router.get("/profile")
def get_profile(db: Session = Depends(get_db)):
    return profile.build_profile(db)


@router.get("/recipes/{recipe_id}/flavor")
def get_recipe_flavor(recipe_id: int, db: Session = Depends(get_db)):
    result = flavors.recipe_flavor(get_recipe_or_404(db, recipe_id).ingredients)
    return {
        "values": [
            {"flavor": f, "label": flavors.LABELS[f], "value": result["values"][f],
             "level": flavors.level(result["values"][f]), "because": result["because"][f]}
            for f in flavors.FLAVORS
        ],
        "unknown": result["unknown"],
    }
