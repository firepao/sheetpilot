from __future__ import annotations

from ..capabilities import DEFAULT_REGISTRY
from ..errors import ErrorCode, SheetPilotError
from ..runtime import TransformManifest, TransformRunner


def dispatch(context, step, results: dict, registry=DEFAULT_REGISTRY):
    if step.kind == "TRANSFORM":
        input_id = step.parameters.get("input")
        if input_id not in results:
            raise SheetPilotError(ErrorCode.PLAN_INVALID, "Transform 输入步骤不存在", {"input": input_id})
        source = step.parameters.get("source")
        if not isinstance(source, str):
            raise SheetPilotError(ErrorCode.PLAN_INVALID, "Transform 缺少脚本源码")
        raw_manifest = dict(step.parameters.get("manifest", {}))
        raw_manifest.setdefault("name", step.id)
        params = dict(step.parameters.get("params", {}))
        result = TransformRunner().run(source, results[input_id], params, TransformManifest(**raw_manifest), context.run_dir)
        results[step.id] = result
        return result
    definition = registry.require(step.handler, getattr(context.engine, "engine_name", "openpyxl"))
    p = definition.validator(dict(step.parameters))
    result = definition.handler(context, p, results)
    results[step.id] = result
    return result
