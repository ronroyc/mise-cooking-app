"""Pydantic schemas for recipe recommendations (see services/recommendations.py)."""
from pydantic import BaseModel

from app.schemas.recipe import MatchColor, RecipeSummary


class Recommendation(BaseModel):
    recipe: RecipeSummary
    score: int             # 0-100 = coverage_points + use_soon_points + taste_points
    coverage_points: int   # up to 70: share of required ingredients on hand
    use_soon_points: int   # up to 20: uses items that expire within 3 days
    taste_points: int      # up to 10: fits the meals you rate 4 or 5 (services/taste.py)
    ready: bool            # every required ingredient is on hand
    color: MatchColor      # green / yellow / red corner tab (matching.match_color)
    have_count: int
    swap_count: int        # of the rest, how many have a swap you can make
    required_count: int
    missing: list[str]
    short: list[str]
    expired: list[str]
    use_soon: list[str]    # inventory items it would use up, soonest first
    reasons: list[str]     # the score in plain words, most important first


class RecommendationList(BaseModel):
    inventory_count: int   # 0 means scores can't mean much yet; the page says so
    recommendations: list[Recommendation]
