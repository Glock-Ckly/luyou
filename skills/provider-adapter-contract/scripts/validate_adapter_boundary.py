from __future__ import annotations

import argparse
import ast
from pathlib import Path


FORBIDDEN = {"routing_table", "dispatcher", "orchestrator"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("adapter")
    args = parser.parse_args()
    path = Path(args.adapter)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = set()
    async_methods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.AsyncFunctionDef):
            async_methods.add(node.name)
    violations = sorted(imports & FORBIDDEN)
    missing = sorted({"execute", "health"} - async_methods)
    if violations or missing:
        print({"adapter": str(path), "forbidden_imports": violations, "missing_async_methods": missing})
        return 1
    print({"adapter": str(path), "status": "valid", "async_methods": sorted(async_methods)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
