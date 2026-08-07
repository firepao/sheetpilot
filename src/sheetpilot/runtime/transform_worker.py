from __future__ import annotations

import json
import sys
from pathlib import Path


ALLOWED_IMPORTS = {"datetime", "math", "re", "statistics"}


def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".", 1)[0]
    if level or root not in ALLOWED_IMPORTS:
        raise ImportError(f"禁止导入: {name}")
    return __import__(name, globals, locals, fromlist, level)


SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate,
    "float": float, "int": int, "isinstance": isinstance, "len": len, "list": list,
    "max": max, "min": min, "range": range, "round": round, "set": set, "sorted": sorted,
    "str": str, "sum": sum, "tuple": tuple, "zip": zip, "__import__": safe_import,
}


def main() -> int:
    root = Path(sys.argv[1])
    payload = json.loads((root / "input.json").read_text(encoding="utf-8"))
    namespace = {"__builtins__": SAFE_BUILTINS}
    source = (root / "task.py").read_text(encoding="utf-8")
    exec(compile(source, "task.py", "exec"), namespace, namespace)
    result = namespace["transform"]({"headers": payload["headers"], "rows": payload["rows"]}, payload["params"])
    (root / "result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
