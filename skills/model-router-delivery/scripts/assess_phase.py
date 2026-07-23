from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run(command: list[str], cwd: Path) -> dict:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    return {
        "command": " ".join(command),
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "tail": (completed.stdout + completed.stderr)[-2000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--phase", default="unnamed-phase")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    checks = [
        run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], repo),
        run([sys.executable, "scripts/test_dashboard_demo.py"], repo),
        run(["git", "diff", "--check"], repo),
    ]
    payload = {"phase": args.phase, "repo": str(repo), "passed": all(item["passed"] for item in checks), "checks": checks}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
