from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo / "scripts"))
    sys.path.insert(0, str(repo / "src"))
    from dashboard_server import simulate_reliability

    baseline = simulate_reliability({"task_type": "implementation", "complexity": "T2"})
    primary = baseline["candidate_chain"][0]
    retryable = simulate_reliability({"task_type": "implementation", "complexity": "T2", "failure_mode": "timeout", "retry_once": True, "failed_models": [primary]})
    authentication = simulate_reliability({"task_type": "implementation", "complexity": "T2", "failure_mode": "authentication", "failed_models": [primary]})
    checks = {
        "retry_then_fallback": [item["action"] for item in retryable["attempts"][:2]] == ["retry", "fallback"],
        "retryable_succeeds": retryable["outcome"] == "success",
        "authentication_fails_fast": authentication["outcome"] == "failed" and len(authentication["attempts"]) == 1,
        "trace_is_preserved": retryable["trace_id"] == retryable["execution_trace_id"],
    }
    print(json.dumps({"passed": all(checks.values()), "checks": checks}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
