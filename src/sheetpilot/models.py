from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


StepKind = Literal["CAPABILITY", "COMPOSITE", "RECIPE", "TRANSFORM", "TASK"]
PlanStrategy = Literal["RECIPE", "COMPOSED", "DYNAMIC_TRANSFORM", "DYNAMIC_TASK"]


@dataclass(frozen=True)
class Requirement:
    id: str
    description: str
    critical: bool = True
    validator: str | None = None


@dataclass(frozen=True)
class RequirementCoverage:
    requirement_id: str
    status: Literal["COVERED", "UNCOVERED", "BLOCKED"]
    by_steps: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass(frozen=True)
class FieldProfile:
    column: str
    header: str
    inferred_type: str
    samples: list[Any] = field(default_factory=list)
    null_ratio: float = 0.0
    number_format: str = "General"
    minimum: Any = None
    maximum: Any = None


@dataclass(frozen=True)
class HeaderCandidate:
    row_start: int
    row_end: int
    confidence: float
    fields: list[FieldProfile]


@dataclass(frozen=True)
class SheetProfile:
    name: str
    visibility: str
    used_range: str
    header_candidates: list[HeaderCandidate]
    formula_count: int
    chart_count: int


@dataclass(frozen=True)
class WorkbookProfile:
    schema_version: str
    input: dict[str, Any]
    sheets: list[SheetProfile]
    risk_objects: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConceptMapping:
    field: str
    column: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    alternatives: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class SemanticTask:
    schema_version: str
    task_id: str
    user_intent: str
    input_file: str
    output_file: str
    source: dict[str, Any]
    concepts: dict[str, ConceptMapping]
    business_definition: dict[str, Any]
    requested_output: dict[str, Any]
    ambiguities: list[dict[str, Any]] = field(default_factory=list)
    confirmations: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SemanticTask":
        data = dict(value)
        data["concepts"] = {k: ConceptMapping(**v) for k, v in data["concepts"].items()}
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HighLevelStep:
    id: str
    op: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class HighLevelPlan:
    schema_version: str
    task_id: str
    strategy: str
    recipe: str | None
    steps: list[HighLevelStep]
    assertions: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "HighLevelPlan":
        steps = []
        for raw in value["steps"]:
            params = dict(raw.get("parameters", {}))
            params.update({k: v for k, v in raw.items() if k not in {"id", "op", "parameters"}})
            steps.append(HighLevelStep(raw["id"], raw["op"], params))
        return cls(value["schema_version"], value["task_id"], value["strategy"], value.get("recipe"), steps, value.get("assertions", []))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionStep:
    id: str
    handler: str
    depends_on: list[str]
    parameters: dict[str, Any]
    expected_reads: list[str] = field(default_factory=list)
    expected_writes: list[str] = field(default_factory=list)
    kind: StepKind = "CAPABILITY"


@dataclass(frozen=True)
class ExecutionPlan:
    schema_version: str
    plan_id: str
    task_id: str
    input_file: str
    output_file: str
    input_sha256: str
    engine: str
    steps: list[ExecutionStep]
    change_budget: dict[str, int]
    required_validations: list[str]
    assertions: list[dict[str, Any]] = field(default_factory=list)
    strategy: PlanStrategy = "COMPOSED"
    requirements: list[Requirement] = field(default_factory=list)
    coverage: list[RequirementCoverage] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ExecutionPlan":
        data = dict(value)
        data["steps"] = [ExecutionStep(**item) for item in data["steps"]]
        data["requirements"] = [Requirement(**item) for item in data.get("requirements", [])]
        data["coverage"] = [RequirementCoverage(**item) for item in data.get("coverage", [])]
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PolicyReason:
    code: str
    message: str
    blocking: bool


@dataclass(frozen=True)
class PolicyDecision:
    decision: Literal["BLOCK", "CONFIRM", "PROCEED"]
    reasons: list[PolicyReason] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    severity: Literal["critical", "important", "advisory"]
    passed: bool
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskResult:
    status: str
    output_file: str | None
    summary: str
    checks: list[ValidationCheck] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def json_ready(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, Path):
        return str(value)
    return value
