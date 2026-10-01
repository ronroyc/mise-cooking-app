"""Recommendation routes.

GET /api/recommendations   recipes ranked by what's in the kitchen
                           (optional ?search=&cuisine=&max_total_time=&limit=&pinned=true)
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.schemas.recommendation import RecommendationList
from app.services import recommendations

router = APIRouter(tags=["recommendations"])


@router.get("/recommendations", response_model=RecommendationList)
def list_recommendations(
    search: Optional[str] = Query(default=None, max_length=100),
    cuisine: Optional[str] = Query(default=None, max_length=50),
    max_total_time: Optional[int] = Query(default=None, ge=0, description="Prep + cook, in minutes"),
    limit: Optional[int] = Query(default=None, ge=1, le=100),
    pinned: bool = Query(default=False, description="Only pinned recipes"),
    db: Session = Depends(get_db),
):
    return recommendations.recommend(db, search, cuisine, max_total_time, limit, pinned_only=pinned)
