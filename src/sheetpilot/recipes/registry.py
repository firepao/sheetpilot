from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..models import HighLevelPlan, SemanticTask
from .operating_summary import OperatingSummaryRecipe


class Recipe(Protocol):
    recipe_id: str
    covers: frozenset[str]

    def match(self, task: SemanticTask) -> bool: ...
    def compile(self, task: SemanticTask) -> HighLevelPlan: ...


@dataclass(frozen=True)
class RecipeMatch:
    recipe: Recipe
    rationale: str


class RecipeRegistry:
    def __init__(self, recipes: tuple[Recipe, ...]):
        ids = [recipe.recipe_id for recipe in recipes]
        if len(ids) != len(set(ids)):
            raise ValueError("Recipe ID 不能重复")
        self._recipes = recipes

    def match(self, task: SemanticTask) -> RecipeMatch | None:
        for recipe in self._recipes:
            if recipe.match(task):
                return RecipeMatch(recipe, f"完整命中稳定 Recipe: {recipe.recipe_id}")
        return None

    def manifest(self) -> list[dict[str, str]]:
        return [{"id": recipe.recipe_id, "kind": "RECIPE", "covers": sorted(recipe.covers)} for recipe in self._recipes]


DEFAULT_RECIPE_REGISTRY = RecipeRegistry((OperatingSummaryRecipe(),))
