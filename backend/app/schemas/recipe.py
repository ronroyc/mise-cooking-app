"""Pydantic schemas: the shape of recipe data going in and out of the API.

"In" schemas validate what the browser sends. Bad data is rejected with a 422
error before it ever reaches the database. "Out" schemas control exactly which
fields the API returns.
"""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.services import units
from app.services.names import match_key


def normalize_name(name: str) -> str:
    """'  Soy   Sauce ' -> 'soy sauce', so the same ingredient is always spelled the same way."""
    return " ".join(name.lower().split())


def check_source_url(value: Optional[str]) -> Optional[str]:
    """Only web addresses, so a link on the recipe page can't run code ("javascript:...")."""
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        raise ValueError("source url must start with http:// or https://")
    return value


def check_no_duplicate_ingredients(ingredients):
    # By match key, so "egg" and "eggs" count as the same ingredient.
    seen = {}
    for item in ingredients:
        key = match_key(item.name)
        if key in seen:
            same = f"'{item.name}'" if item.name == seen[key] else f"'{seen[key]}' and '{item.name}'"
            raise ValueError(f"{same} {'is' if item.name == seen[key] else 'are'} listed more than once")
        seen[key] = item.name
    return ingredients


# ---------- Input ----------

class RecipeIngredientIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    quantity: Optional[float] = Field(default=None, gt=0, le=10000, allow_inf_nan=False)
    unit: Optional[str] = Field(default=None, max_length=20)
    optional: bool = False
    preparation_note: Optional[str] = Field(default=None, max_length=200)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return normalize_name(value)

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, value: Optional[str]) -> Optional[str]:
        return units.normalize_unit(value)  # "Tablespoons" -> "tbsp"

    @field_validator("preparation_note")
    @classmethod
    def blank_note_to_none(cls, value: Optional[str]) -> Optional[str]:
        return value or None

    @model_validator(mode="after")
    def unit_needs_quantity(self):
        if self.unit and self.quantity is None:
            raise ValueError(f"'{self.name}' has a unit but no quantity")
        return self


class RecipeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    servings: int = Field(gt=0, le=100)
    prep_time: int = Field(ge=0, le=1440)
    cook_time: int = Field(ge=0, le=1440)
    cuisine: Optional[str] = Field(default=None, max_length=50)
    instructions: str = Field(min_length=1, max_length=10000)
    ingredients: list[RecipeIngredientIn] = Field(min_length=1)
    source_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("cuisine")
    @classmethod
    def clean_cuisine(cls, value: Optional[str]) -> Optional[str]:
        return value.title() if value else None  # "japanese" -> "Japanese"

    @field_validator("source_url")
    @classmethod
    def clean_source_url(cls, value: Optional[str]) -> Optional[str]:
        return check_source_url(value)

    @field_validator("ingredients")
    @classmethod
    def no_duplicates(cls, value):
        return check_no_duplicate_ingredients(value)


class RecipeUpdate(BaseModel):
    """PATCH: every field is optional, and only the fields you send are changed.

    If `ingredients` is sent, it replaces the recipe's whole ingredient list.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    servings: Optional[int] = Field(default=None, gt=0, le=100)
    prep_time: Optional[int] = Field(default=None, ge=0, le=1440)
    cook_time: Optional[int] = Field(default=None, ge=0, le=1440)
    cuisine: Optional[str] = Field(default=None, max_length=50)
    instructions: Optional[str] = Field(default=None, min_length=1, max_length=10000)
    ingredients: Optional[list[RecipeIngredientIn]] = Field(default=None, min_length=1)
    source_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("cuisine")
    @classmethod
    def clean_cuisine(cls, value: Optional[str]) -> Optional[str]:
        return value.title() if value else None

    @field_validator("source_url")
    @classmethod
    def clean_source_url(cls, value: Optional[str]) -> Optional[str]:
        return check_source_url(value)

    @field_validator("ingredients")
    @classmethod
    def no_duplicates(cls, value):
        return check_no_duplicate_ingredients(value) if value is not None else None

    @model_validator(mode="after")
    def required_fields_not_null(self):
        # Sending {"title": null} would otherwise wipe out a required field.
        for field in ("title", "servings", "prep_time", "cook_time", "instructions", "ingredients"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be empty")
        return self


# ---------- Output ----------

class RecipeIngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # read values straight off the SQLAlchemy object

    id: int
    name: str
    category: Optional[str]
    quantity: Optional[float]
    unit: Optional[str]
    optional: bool
    preparation_note: Optional[str]

    # Ready-to-show text, so every page formats amounts the same way.
    @computed_field
    @property
    def amount_text(self) -> str:
        """'1 1/2 cups', '3 cloves', '2' (for 2 eggs), or '' for "to taste"."""
        return units.format_amount(self.quantity, self.unit)

    @computed_field
    @property
    def display_name(self) -> str:
        """'eggs' when there are 2 of them; otherwise the name as stored."""
        return units.pluralize_name(self.name, self.quantity, self.unit)


class RecipeSummary(BaseModel):
    """Lightweight version for the recipe list (no ingredients or instructions)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str]
    servings: int
    prep_time: int
    cook_time: int
    total_time: int
    cuisine: Optional[str]
    times_cooked: int = 0
    last_cooked: Optional[date] = None
    average_rating: Optional[float] = None  # 1-5, from cooking history
    pinned: bool = False
    photo_url: Optional[str] = None  # None: the card shows a plain colored cover
    source_url: Optional[str] = None  # imported recipes link back to the site


class SwapOption(BaseModel):
    """A swap from the hand-written table (services/substitutions.py)."""

    uses: list[str]  # all of these are needed: ["milk", "lemon juice"]
    amount: str
    note: str
    have: bool       # every one of them is in the kitchen


class IngredientMatch(BaseModel):
    """One recipe ingredient compared with the inventory (see services/matching.py)."""

    name: str
    display_name: str
    amount_text: str
    optional: bool
    status: Literal["have", "short", "expired", "staple", "missing"]
    inventory_item_id: Optional[int]
    inventory_name: Optional[str]         # can differ from `name`: "eggs" in the kitchen, "egg" in the recipe
    inventory_amount_text: Optional[str]  # "2 cups", "6 eggs", "some"
    expires_in_days: Optional[int]        # of the inventory item; negative once expired
    note: Optional[str]                   # plain-words explanation for short/expired/uncomparable
    swaps: list[SwapOption] = []          # for ingredients you don't have: ones you can make first


MatchColor = Literal["green", "yellow", "red"]


class RecipeMatchOut(BaseModel):
    recipe_id: int
    servings: int
    required_count: int  # ingredients that aren't optional
    have_count: int      # of those, how many are "have" or "staple"
    ready: bool          # every required ingredient is "have" or "staple"
    color: MatchColor    # the corner tab on recipe cards (matching.match_color)
    swap_count: int = 0  # required ingredients you don't have, but have a swap for
    ingredients: list[IngredientMatch]


class RecipeOut(RecipeSummary):
    """Full recipe for the detail page."""

    instructions: str
    base_servings: int  # what the recipe was written for; `servings` differs when scaled
    created_at: datetime
    updated_at: datetime
    ingredients: list[RecipeIngredientOut]


# ---------- Importing from a website (services/recipe_import.py) ----------

class RecipeImportRequest(BaseModel):
    url: str = Field(min_length=1, max_length=500)


class RecipeImportDataRequest(BaseModel):
    """From the "Save to Slice'd" Safari button, which reads the page's recipe data itself."""

    url: str = Field(min_length=1, max_length=500)
    recipe: dict


class RecipeImportDraft(BaseModel):
    """A recipe read from a website, to fill the form. Not saved yet."""

    title: str
    description: Optional[str]
    cuisine: Optional[str]
    servings: int
    prep_time: int
    cook_time: int
    instructions: str
    ingredients: list[dict]   # name, quantity, unit, preparation_note, optional
    image_url: Optional[str]  # the site's photo, which can be saved with the recipe
    source_url: str
    warnings: list[str]       # what the cook should check before saving


class PhotoFromUrlRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
