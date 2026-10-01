"""Pydantic schemas for cooking history and ratings."""
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def blank_to_none(value: Optional[str]) -> Optional[str]:
    return value or None


class CookedCreate(BaseModel):
    """POST /recipes/{id}/cooked."""

    model_config = ConfigDict(str_strip_whitespace=True)

    servings: Optional[int] = Field(default=None, gt=0, le=100)  # default: the recipe's own
    cooked_on: Optional[date] = None                             # default: today
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    notes: Optional[str] = Field(default=None, max_length=2000)
    update_inventory: bool = True  # take what the recipe used out of the inventory
    leftover_servings: Optional[int] = Field(default=None, gt=0, le=50)  # save these to the fridge

    _clean_notes = field_validator("notes")(blank_to_none)

    @field_validator("cooked_on")
    @classmethod
    def not_in_future(cls, value: Optional[date]) -> Optional[date]:
        if value is not None and value > date.today():
            raise ValueError("cooked_on can't be in the future")
        return value


class CookingLogUpdate(BaseModel):
    """PATCH: rate it later, or fix the notes or date. Send null to clear rating or notes."""

    model_config = ConfigDict(str_strip_whitespace=True)

    rating: Optional[int] = Field(default=None, ge=1, le=5)
    notes: Optional[str] = Field(default=None, max_length=2000)
    cooked_on: Optional[date] = None

    _clean_notes = field_validator("notes")(blank_to_none)

    @model_validator(mode="after")
    def check_fields(self):
        if "cooked_on" in self.model_fields_set:
            if self.cooked_on is None:
                raise ValueError("cooked_on cannot be empty")
            if self.cooked_on > date.today():
                raise ValueError("cooked_on can't be in the future")
        return self


class CookingLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipe_id: Optional[int]  # None if the recipe was deleted since
    recipe_title: str
    cooked_on: date
    servings: int
    rating: Optional[int]
    notes: Optional[str]


class CookedResult(BaseModel):
    log: CookingLogOut
    inventory_changes: list[str]  # plain sentences: "Used 2 cups rice; 4 cups left."
