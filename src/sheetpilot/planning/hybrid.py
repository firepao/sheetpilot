from __future__ import annotations

from dataclasses import dataclass, field

from ..capabilities import DEFAULT_REGISTRY
from ..models import Requirement, RequirementCoverage, SemanticTask
from ..recipes import DEFAULT_RECIPE_REGISTRY


@dataclass(frozen=True)
class PlanningDecision:
    strategy: str
    components: list[str]
    coverage: list[RequirementCoverage]
    rationale: list[str] = field(default_factory=list)

    @property
    def executable(self) -> bool:
        return all(item.status == "COVERED" for item in self.coverage)


class HybridPlanner:
    def __init__(self, component_registry=DEFAULT_REGISTRY, recipe_registry=DEFAULT_RECIPE_REGISTRY):
        self.components = component_registry
        self.recipes = recipe_registry

    def choose(self, task: SemanticTask, requirements: list[Requirement]) -> PlanningDecision:
        recipe_match = self.recipes.match(task)
        required_ids = {item.id for item in requirements}
        if recipe_match and required_ids.issubset(recipe_match.recipe.covers):
            coverage = [RequirementCoverage(item.id, "COVERED", [recipe_match.recipe.recipe_id], recipe_match.rationale) for item in requirements]
            return PlanningDecision("RECIPE", [recipe_match.recipe.recipe_id], coverage, [recipe_match.rationale])

        selected: list[str] = []
        coverage: list[RequirementCoverage] = []
        definitions = self.components.definitions()
        for requirement in requirements:
            matches = [item for item in definitions if requirement.id in item.covers]
            if matches:
                chosen = sorted(matches, key=lambda item: (item.kind != "COMPOSITE", item.name))[0]
                if chosen.name not in selected:
                    selected.append(chosen.name)
                coverage.append(RequirementCoverage(requirement.id, "COVERED", [chosen.name], f"由 {chosen.kind} 覆盖"))
            else:
                coverage.append(RequirementCoverage(requirement.id, "UNCOVERED", [], "注册表中没有声明可覆盖该要求的组件"))
        if all(item.status == "COVERED" for item in coverage):
            return PlanningDecision("COMPOSED", selected, coverage, ["使用最少的已注册 Composite/Capability 组合"])
        return PlanningDecision("DYNAMIC_TRANSFORM", selected, coverage, ["固定组件存在缺口；仅当缺口可表达为 TableData 变换时允许生成 Transform"])
