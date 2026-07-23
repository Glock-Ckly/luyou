#!/usr/bin/env python3
"""luyou 路由分发台 - 本机 http://127.0.0.1:1785"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = ROOT / "dashboard"
PORT = 1785


def _src_imports():
    source_path = str(ROOT / "src")
    if source_path not in sys.path:
        sys.path.insert(0, source_path)


def _git_info() -> dict:
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return {"branch": branch, "commit": commit}
    except Exception:
        return {"branch": "-", "commit": "-"}


def _budget_ratio() -> float:
    """Read budget pressure with a short timeout so the single-threaded server stays responsive."""
    import concurrent.futures

    def _fetch() -> float:
        _src_imports()
        from budget_adapter import get_budget_ratio_sync

        return float(get_budget_ratio_sync())

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_fetch).result(timeout=3.0)
    except Exception:
        return 0.0


def build_catalog() -> dict:
    _src_imports()
    from routing_table import MODEL_CATALOG, TASK_POLICY, TASK_TO_MODEL

    route_usage: dict[str, int] = {}
    routes = []
    for (task_type, complexity), config in sorted(TASK_TO_MODEL.items()):
        chain = [str(config["primary"]), *map(str, config["fallback"])]
        for model in chain:
            route_usage[model] = route_usage.get(model, 0) + 1
        routes.append({
            "task_type": task_type,
            "complexity": complexity,
            "primary": chain[0],
            "fallback": chain[1:],
            "executor": str(TASK_POLICY[task_type]["executor"]),
        })

    providers: dict[str, dict] = {}
    for model_id, details in sorted(MODEL_CATALOG.items()):
        provider_id = "local" if model_id == "cursor_queue" else model_id.split("/", 1)[0]
        model = {
            "id": model_id,
            "name": model_id.split("/", 1)[-1],
            "provider": provider_id,
            "tier": details["tier"],
            "cost_per_mtok": details["cost_per_mtok"],
            "route_usage": route_usage.get(model_id, 0),
        }
        provider = providers.setdefault(provider_id, {
            "id": provider_id,
            "name": provider_id.title(),
            "status": "configured",
            "models": [],
        })
        provider["models"].append(model)

    policies = []
    for task_type, policy in TASK_POLICY.items():
        cost_level = policy["cost_level"]
        policies.append({
            "task_type": task_type,
            "executor": str(policy["executor"]),
            "floor": str(policy["floor"]),
            "cost_level": getattr(cost_level, "value", str(cost_level)),
        })

    return {
        "providers": list(providers.values()),
        "models": [model for provider in providers.values() for model in provider["models"]],
        "policies": policies,
        "routes": routes,
        "provider_contract": [
            "接受统一 ModelRequest",
            "返回统一 ModelResponse",
            "将 Provider 错误映射为标准错误类型",
            "遵守 Timeout 与取消信号",
            "不得在 Adapter 内做路由决策",
        ],
    }


def build_meta() -> dict:
    catalog = build_catalog()
    return {
        "project_path": str(ROOT),
        "git": _git_info(),
        "budget_ratio": _budget_ratio(),
        "stats": {
            "providers": len(catalog["providers"]),
            "models": len(catalog["models"]),
            "policies": len(catalog["policies"]),
            "routes": len(catalog["routes"]),
        },
    }


def _run_dispatch(prompt: str, workdir: str) -> dict:
    _src_imports()
    from dispatcher import dispatch_prompt

    return asyncio.run(dispatch_prompt(prompt, workdir=workdir))


def _cursor_queue_pending() -> list[dict]:
    _src_imports()
    try:
        from cursor_queue import list_tasks

        return list_tasks("pending")
    except Exception:
        return []


def build_specs() -> dict:
    return {
        "domains": [
            {"name": "Gateway", "owns": "HTTP、校验、响应标准化", "excludes": "模型选择与 Provider 细节"},
            {"name": "Routing", "owns": "分类、策略、预算、模型决策", "excludes": "直接调用 Provider API"},
            {"name": "Provider", "owns": "模型目录、能力、成本、适配契约", "excludes": "用户认证与路由决策"},
            {"name": "Execution", "owns": "执行器、超时、结果归一化", "excludes": "修改路由业务规则"},
            {"name": "Skill", "owns": "可复用、可独立测试的能力", "excludes": "自主规划与无限循环"},
            {"name": "Agent", "owns": "受约束的目标分解与决策增强", "excludes": "成为基础路由单点依赖"},
        ],
        "request_lifecycle": ["RECEIVED", "VALIDATED", "ROUTING", "SELECTED", "EXECUTING", "SUCCESS"],
        "failure_lifecycle": ["EXECUTION_ERROR", "CLASSIFIED", "RETRY", "FALLBACK", "NEXT_PROVIDER", "SUCCESS_OR_FAILED"],
        "adrs": [
            {
                "title": "先模块化单体，后服务拆分",
                "decision": "先验证领域边界与 Contract，再按真实扩展压力引入 gRPC。",
                "consequence": "Demo 可直接运行，同时保留 Gateway / Routing 拆分路径。",
            },
            {
                "title": "规则路由是可靠性基础",
                "decision": "Task Type、Complexity、Budget 先由确定性策略决策。",
                "consequence": "无模型调用时仍可解释、测试和复现路由结果。",
            },
            {
                "title": "Agent 是增强层",
                "decision": "Agent 只做受约束规划，Skill 保持独立、确定、可测试。",
                "consequence": "Agent 失败不会阻断基础路由与 Fallback。",
            },
        ],
        "quality_gates": [
            "Specification 先于实现",
            "Routing 与 Budget 单元测试",
            "Provider Contract Test",
            "端到端 Acceptance",
            "Trace ID 与结构化错误",
        ],
    }


def simulate_reliability(payload: dict) -> dict:
    _src_imports()
    from model_router.adapters.providers.fault_injecting_provider import FaultInjectingProvider
    from model_router.application.execution_service import ExecutionService
    from model_router.domain.models import ModelId, RetryPolicy, TraceId
    from routing_table import route

    task_type = str(payload.get("task_type") or "implementation")
    complexity = str(payload.get("complexity") or "T2")
    try:
        budget_ratio = min(1.0, max(0.0, float(payload.get("budget_ratio", 0.2))))
    except (TypeError, ValueError):
        raise ValueError("budget_ratio must be a number between 0 and 1") from None

    failure_mode = str(payload.get("failure_mode") or "provider_unavailable")
    failed_models = {str(model) for model in payload.get("failed_models", [])}
    retry_once = bool(payload.get("retry_once", True))
    decision = route(task_type, complexity=complexity, budget_ratio=budget_ratio)
    candidates = list(dict.fromkeys([decision.primary, *decision.fallback]))
    trace_id = TraceId.new()
    execution = asyncio.run(
        ExecutionService(
            FaultInjectingProvider(
                failed_models=failed_models,
                failure_mode=failure_mode,
            ),
            RetryPolicy(max_retries=1 if retry_once else 0),
            timeout_seconds=1,
        ).execute(
            trace_id=trace_id,
            prompt="reliability fault-injection scenario",
            candidates=[ModelId.parse(model) for model in candidates],
        )
    )
    attempts = [
        {
            "model": attempt.model_id.value,
            "attempt": attempt.attempt,
            "status": attempt.status,
            "error_type": attempt.error_type,
            "action": attempt.action,
            "latency_ms": attempt.latency_ms,
        }
        for attempt in execution.attempts
    ]

    return {
        "trace_id": trace_id.value,
        "execution_trace_id": execution.trace_id.value,
        "task_type": decision.task_type,
        "complexity": decision.complexity,
        "budget_zone": decision.budget_zone,
        "executor": decision.executor,
        "candidate_chain": candidates,
        "failed_models": sorted(failed_models),
        "failure_mode": failure_mode,
        "attempts": attempts,
        "selected_model": execution.selected_model.value if execution.selected_model else None,
        "outcome": execution.outcome,
        "final_error_type": execution.final_error_type,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError("invalid JSON") from None

    def _static_response(self, request_path: str):
        relative = "index.html" if request_path in ("", "/") else unquote(request_path.lstrip("/"))
        candidate = (DASHBOARD / relative).resolve()
        try:
            candidate.relative_to(DASHBOARD.resolve())
        except ValueError:
            self.send_response(403)
            self.end_headers()
            return

        if not candidate.is_file():
            self.send_response(404)
            self.end_headers()
            return

        body = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type == "application/javascript":
            content_type = f"{content_type}; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            self._do_get()
        except (ConnectionAbortedError, BrokenPipeError):
            pass
        except Exception as error:
            self._json_response(500, {"error": str(error)})

    def do_POST(self):
        try:
            self._do_post()
        except (ConnectionAbortedError, BrokenPipeError):
            pass
        except ValueError as error:
            self._json_response(400, {"error": str(error)})
        except Exception as error:
            self._json_response(500, {"error": str(error)})

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _do_get(self):
        path = urlparse(self.path).path

        if path == "/api/meta":
            self._json_response(200, build_meta())
            return

        if path == "/api/catalog":
            self._json_response(200, build_catalog())
            return

        if path == "/api/specs":
            self._json_response(200, build_specs())
            return

        if path == "/api/cursor/queue":
            self._json_response(200, {"pending": _cursor_queue_pending()})
            return

        self._static_response(path)

    def _do_post(self):
        path = urlparse(self.path).path
        body = self._read_json()

        if path == "/api/reliability/simulate":
            self._json_response(200, simulate_reliability(body))
            return

        if path != "/api/route":
            self._json_response(404, {"error": "not found"})
            return

        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("prompt is required")

        workdir = (body.get("workdir") or str(ROOT)).strip()
        result = _run_dispatch(prompt, workdir)
        self._json_response(200, result)


def main():
    host = "127.0.0.1"
    server = ThreadingHTTPServer((host, PORT), Handler)
    print(f"luyou five-page demo -> http://{host}:{PORT}")
    print("API -> GET /api/meta | /api/catalog | /api/specs")
    print("API -> POST /api/route | /api/reliability/simulate")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
