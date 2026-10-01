# Importing the models here registers their tables with Base.metadata,
# so Base.metadata.create_all() knows which tables to create.
from app.models.grocery import GroceryItem
from app.models.history import CookingLog
from app.models.inventory import InventoryItem
from app.models.recipe import Ingredient, Recipe, RecipeIngredient

__all__ = ["CookingLog", "GroceryItem", "Ingredient", "InventoryItem", "Recipe", "RecipeIngredient"]
