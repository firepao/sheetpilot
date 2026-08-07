from __future__ import annotations

from dataclasses import dataclass

from ..models import SemanticTask
from ..recipes import DEFAULT_RECIPE_REGISTRY


@dataclass(frozen=True)
class RouteDecision:
    strategy: str
    recipe_id: str | None
    uncovered_requirements: list[str]


def route(task: SemanticTask, registry=DEFAULT_RECIPE_REGISTRY) -> RouteDecision:
    match = registry.match(task)
    if match:
        return RouteDecision("RECIPE", match.recipe.recipe_id, [])
    return RouteDecision("COMPOSED", None, ["operating_summary"])
