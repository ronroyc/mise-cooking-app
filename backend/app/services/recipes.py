"""Recipe business logic: everything that reads or writes recipes in the database.

The API layer (app/api/recipes.py) handles HTTP; this file handles the data.
Keeping them apart means this logic can be reused (e.g. by the seed script)
and tested without going through HTTP.
"""
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Ingredient, Recipe, RecipeIngredient
from app.models.recipe import utc_now
from app.schemas.recipe import RecipeCreate, RecipeIngredientIn, RecipeOut, RecipeUpdate
from app.services import units
from app.services.names import match_key


# For queries that read many recipes' ingredients or cooking history. Without it, each
# recipe's ingredients are a separate query when first used ("N+1 queries"): with 800
# recipes, the home page made over 4,000 queries. This loads them in three.
WITH_DETAILS = (
    selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
    selectinload(Recipe.cook_logs),
)


def find_ingredient(db: Session, name: str) -> Optional[Ingredient]:
    """The ingredient row for this name: an exact match, or one with the same match key
    ("eggs" finds "egg", "scallions" finds "green onion")."""
    ingredient = db.scalar(select(Ingredient).where(Ingredient.name == name))
    if ingredient is not None:
        return ingredient
    key = match_key(name)
    # The ingredients table is small (one row per distinct ingredient), so checking
    # every key in Python is simpler than storing keys in the database.
    return next((i for i in db.scalars(select(Ingredient).order_by(Ingredient.id)) if match_key(i.name) == key), None)


def get_or_create_ingredient(
    db: Session, name: str, category: Optional[str] = None, exact: bool = False
) -> Ingredient:
    """Reuse the existing ingredient row if there is one, so 'garlic' exists only once.

    exact=True skips match-key lookup, for when the user deliberately picks a new spelling.
    """
    if exact:
        ingredient = db.scalar(select(Ingredient).where(Ingredient.name == name))
    else:
        ingredient = find_ingredient(db, name)
    if ingredient is None:
        ingredient = Ingredient(name=name, category=category)
        db.add(ingredient)
        db.flush()  # sends the INSERT now so the new row gets an id
    elif category and not ingredient.category:
        ingredient.category = category
    return ingredient


def _build_ingredient_links(db: Session, items: list[RecipeIngredientIn]) -> list[RecipeIngredient]:
    # Look up (or create) every ingredient first. get_or_create_ingredient can flush,
    # and flushing while half-built RecipeIngredient objects exist makes SQLAlchemy warn.
    ingredients = [get_or_create_ingredient(db, item.name) for item in items]
    return [
        RecipeIngredient(
            ingredient=ingredient,
            quantity=item.quantity,
            unit=item.unit,
            optional=item.optional,
            preparation_note=item.preparation_note,
        )
        for ingredient, item in zip(ingredients, items)
    ]


def list_recipes(
    db: Session,
    search: Optional[str] = None,
    cuisine: Optional[str] = None,
    max_total_time: Optional[int] = None,
    pinned_only: bool = False,
) -> list[Recipe]:
    # Sort by the lowercase title: SQLite puts "T" before "a" otherwise,
    # so "Chicken Teriyaki" would come before "Chicken and Vegetable Stir-Fry".
    query = select(Recipe).options(*WITH_DETAILS).order_by(func.lower(Recipe.title))

    if search and search.strip():
        term = search.strip().lower()
        # Match the title, the description, or any ingredient name.
        # autoescape=True makes characters like % and _ match literally.
        query = query.where(
            or_(
                func.lower(Recipe.title).contains(term, autoescape=True),
                func.lower(Recipe.description).contains(term, autoescape=True),
                Recipe.ingredients.any(
                    RecipeIngredient.ingredient.has(Ingredient.name.contains(term, autoescape=True))
                ),
            )
        )
    if cuisine and cuisine.strip():
        query = query.where(func.lower(Recipe.cuisine) == cuisine.strip().lower())
    if max_total_time is not None:
        query = query.where(Recipe.prep_time + Recipe.cook_time <= max_total_time)
        # No times anywhere in the recipe: it isn't "quick", it's unknown.
        query = query.where(or_(Recipe.time_status.is_(None), Recipe.time_status != "unknown"))
    if pinned_only:
        query = query.where(Recipe.pinned_at.is_not(None))

    return list(db.scalars(query))


def list_cuisines(db: Session) -> list[str]:
    query = select(Recipe.cuisine).where(Recipe.cuisine.is_not(None)).distinct().order_by(Recipe.cuisine)
    return list(db.scalars(query))


def get_recipe(db: Session, recipe_id: int) -> Optional[Recipe]:
    return db.get(Recipe, recipe_id)


def create_recipe(db: Session, data: RecipeCreate) -> Recipe:
    recipe = Recipe(**data.model_dump(exclude={"ingredients"}))
    recipe.ingredients = _build_ingredient_links(db, data.ingredients)
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


def update_recipe(db: Session, recipe: Recipe, data: RecipeUpdate) -> Recipe:
    # exclude_unset: only touch fields the client actually sent.
    changes = data.model_dump(exclude_unset=True, exclude={"ingredients"})
    # Typing in real times or servings replaces the estimate. The form sends every
    # field, so only a changed value counts.
    if any(field in changes and changes[field] != getattr(recipe, field) for field in ("prep_time", "cook_time")):
        recipe.time_status = None
    if "servings" in changes and changes["servings"] != recipe.servings:
        recipe.servings_estimated = None
    for field, value in changes.items():
        setattr(recipe, field, value)

    if data.ingredients is not None:
        recipe.ingredients.clear()
        # Delete the old rows *before* adding new ones. Otherwise re-adding an
        # ingredient the recipe already had breaks the (recipe_id, ingredient_id)
        # unique constraint, because SQLAlchemy would run the INSERTs first.
        db.flush()
        recipe.ingredients.extend(_build_ingredient_links(db, data.ingredients))

    recipe.updated_at = utc_now()  # also bump it when only ingredients changed
    db.commit()
    db.refresh(recipe)
    return recipe


def scale_recipe(recipe: RecipeOut, servings: int) -> RecipeOut:
    """The recipe resized to `servings`. "To taste" amounts stay as they are.

    After scaling, amounts move to a friendlier unit when there's a clean one
    (6 tsp -> 2 tbsp). At the original size nothing changes, so the recipe reads
    the way it was written.
    """
    if servings == recipe.base_servings:
        return recipe
    factor = servings / recipe.base_servings
    ingredients = []
    for item in recipe.ingredients:
        if item.quantity is not None:
            quantity, unit = units.tidy(item.quantity * factor, item.unit)
            item = item.model_copy(update={"quantity": round(quantity, 4), "unit": unit})
        ingredients.append(item)
    return recipe.model_copy(update={"servings": servings, "ingredients": ingredients})


def set_pinned(db: Session, recipe: Recipe, pinned: bool) -> Recipe:
    """Pin keeps the first pin time, so pinning twice changes nothing."""
    if pinned and recipe.pinned_at is None:
        recipe.pinned_at = utc_now()
    elif not pinned:
        recipe.pinned_at = None
    db.commit()
    return recipe


def delete_recipe(db: Session, recipe: Recipe) -> None:
    db.delete(recipe)  # its recipe_ingredients rows are deleted too (cascade)
    db.commit()
