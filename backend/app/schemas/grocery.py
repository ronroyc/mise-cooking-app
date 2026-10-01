"""Pydantic schemas for the grocery list."""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.schemas.recipe import normalize_name
from app.services import units


class GroceryItemCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    quantity: Optional[float] = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    unit: Optional[str] = Field(default=None, max_length=20)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return normalize_name(value)

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, value: Optional[str]) -> Optional[str]:
        return units.normalize_unit(value)

    @model_validator(mode="after")
    def unit_needs_quantity(self):
        if self.unit and self.quantity is None:
            raise ValueError(f"'{self.name}' has a unit but no quantity")
        return self


class GroceryItemUpdate(BaseModel):
    """PATCH: tick an item off, or change its amount."""

    model_config = ConfigDict(str_strip_whitespace=True)

    checked: Optional[bool] = None
    quantity: Optional[float] = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    unit: Optional[str] = Field(default=None, max_length=20)

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, value: Optional[str]) -> Optional[str]:
        return units.normalize_unit(value)

    @model_validator(mode="after")
    def check_fields(self):
        if "checked" in self.model_fields_set and self.checked is None:
            raise ValueError("checked cannot be empty")
        # Only checkable here when both are sent; the service checks the combined result.
        if self.unit and "quantity" in self.model_fields_set and self.quantity is None:
            raise ValueError("unit needs a quantity")
        return self


class GroceryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: Optional[str]
    quantity: Optional[float]
    unit: Optional[str]
    checked: bool
    for_recipes: Optional[str]

    @computed_field
    @property
    def amount_text(self) -> str:
        """'1 1/2 cups', '6 eggs', or 'some'."""
        return units.describe_amount(self.quantity, self.unit, self.name)

    @computed_field
    @property
    def quantity_text(self) -> str:
        """Just the amount, to show next to the name: '1 1/2 cups', '6', or ''."""
        return units.format_amount(self.quantity, self.unit)


class AddFromRecipeResult(BaseModel):
    added: list[GroceryItemOut]  # rows added or topped up
    skipped_optional: int        # optional ingredients not added
    message: str


class StockResult(BaseModel):
    messages: list[str]  # one sentence per item moved into the inventory
