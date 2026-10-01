"""Pydantic schemas for inventory items going in and out of the API."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.schemas.recipe import normalize_name
from app.services import units

Location = Literal["pantry", "fridge", "freezer"]


# ---------- Input ----------

class InventoryItemCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    quantity: Optional[float] = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    unit: Optional[str] = Field(default=None, max_length=20)
    location: Location = "pantry"
    expiration_date: Optional[date] = None
    # Only used when this is a brand-new ingredient that has no category yet.
    category: Optional[str] = Field(default=None, max_length=50)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return normalize_name(value)

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, value: Optional[str]) -> Optional[str]:
        return units.normalize_unit(value)

    @field_validator("location", mode="before")
    @classmethod
    def lowercase_location(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("category")
    @classmethod
    def blank_category_to_none(cls, value: Optional[str]) -> Optional[str]:
        return value or None

    @model_validator(mode="after")
    def unit_needs_quantity(self):
        if self.unit and self.quantity is None:
            raise ValueError(f"'{self.name}' has a unit but no quantity")
        return self


class InventoryItemUpdate(BaseModel):
    """PATCH: only the fields you send are changed.

    Send "quantity": null to switch back to "some", or "expiration_date": null to clear the date.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    quantity: Optional[float] = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    unit: Optional[str] = Field(default=None, max_length=20)
    location: Optional[Location] = None
    expiration_date: Optional[date] = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: Optional[str]) -> Optional[str]:
        return normalize_name(value) if value is not None else None

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, value: Optional[str]) -> Optional[str]:
        return units.normalize_unit(value)

    @field_validator("location", mode="before")
    @classmethod
    def lowercase_location(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def check_fields(self):
        for field in ("name", "location"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be empty")
        # Only checkable here when both are sent; the service checks the combined result.
        if self.unit and "quantity" in self.model_fields_set and self.quantity is None:
            raise ValueError("unit needs a quantity")
        return self


# ---------- Output ----------

class InventoryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: Optional[str]
    quantity: Optional[float]
    unit: Optional[str]
    location: str
    expiration_date: Optional[date]
    days_until_expiration: Optional[int]
    expiration_status: Optional[Literal["expired", "expiring_soon", "fresh"]]
    updated_at: datetime

    @computed_field
    @property
    def amount_text(self) -> str:
        """'1 1/2 cups', '6 eggs', or 'some' when the amount isn't tracked."""
        return units.describe_amount(self.quantity, self.unit, self.name)


class IngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: Optional[str]


# ---------- AI ingredient recognition ----------

class IdentifyRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return normalize_name(value)


class IngredientSuggestion(BaseModel):
    is_food: bool
    name: str                       # the clean name to save it under
    matches_existing: Optional[str]  # an ingredient Mise already knows, if it's the same thing
    category: str
    typical_location: str
    shelf_life_days: Optional[int]
    description: str


class IdentifyResponse(BaseModel):
    name: str                  # what the user typed, normalized; the stored name when known ("eggs" -> "egg")
    known: bool                # already in Mise, so no AI call was needed
    category: Optional[str]    # set when known
    ai_available: bool
    suggestion: Optional[IngredientSuggestion]
    message: Optional[str]     # why there's no suggestion, in plain words
