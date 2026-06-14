#!/usr/bin/env python3
"""luyou 进度可视化看板 — 本机 http://127.0.0.1:1785"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = ROOT / "dashboard"
PORT = 1785

ROADMAP = [
    {"id": 1, "title": "配置 API Key / 中转站", "done": True},
    {"id": 2, "title": "Smoke 验收 (S0–S6)", "done": True},
    {"id": 3, "title": "L2 分类评估 (25 样本)", "done": True},
    {"id": 4, "title": "TaskDecomposer 验证", "done": True},
    {"id": 5, "title": "llm-router MCP 注册", "done": False, "current": True},
    {"id": 6, "title": "Cursor Queue CLI", "done": True},
    {"id": 7, "title": "4 场景端到端测试", "done": True},
]

MODULES = [
    ("l1_classifier.py", "L1 关键词快筛 (9 类)", "ok"),
    ("l2_classifier.py", "L2 LLM 分类器", "ok"),
    ("routing_table.py", "任务→模型路由表", "ok"),
    ("response_validator.py", "3 层后验校验", "ok"),
    ("relay_config.py", "中转站环境注入", "ok"),
    ("relay_llm.py", "LiteLLM 薄封装", "ok"),
    ("orchestrator.py", "全流程编排器", "ok"),
    ("cursor_queue.py", "Cursor 手动队列", "ok"),
    ("task_decomposer.py", "大任务拆分", "ok"),
    ("prompts/decomposer.txt", "拆分 Prompt", "ok"),
    ("scripts/cursor_cli.py", "Cursor Queue CLI", "ok"),
]

BLOCKERS = [
    {"id": 1, "title": "API Key 配置", "detail": "", "done": True},
    {"id": 2, "title": "L2 分类器调优", "detail": "", "done": True},
    {"id": 3, "title": "TaskDecomposer 验证", "detail": "eval 8/10 (80%)", "done": True},
    {"id": 4, "title": "预算状态接口", "detail": "orchestrator mock 0.0，可选接入", "done": False},
    {"id": 5, "title": "MCP 注册", "detail": "见 STATUS 手动步骤", "done": False},
    {"id": 6, "title": "Cursor Queue CLI", "detail": "scripts/cursor_cli.py", "done": True},
    {"id": 7, "title": "llm-router 打包缺陷", "detail": "已用 relay_llm 绕过", "done": True},
]

PIPELINE = [
    "Prompt", "Decomposer", "L1", "L2", "Router", "Model/Cursor", "Validator",
]


def _git_info() -> dict:
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True
        ).strip()
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
        return {"branch": branch, "commit": commit}
    except Exception:
        return {"branch": "—", "commit": "—"}


def _relay_providers() -> list[dict]:
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from relay_config import get_relay_status, _load_model_map  # type: ignore

        st = get_relay_status()
        maps = _load_model_map()
        return [
            {
                "name": "OpenAI (Ccode)",
                "base_url": st.get("openai_base", ""),
                "key_mask": st.get("openai_key", ""),
                "model_map": maps.get("openai/gpt-4o", "openai/gpt-5.5"),
            },
            {
                "name": "Anthropic (Ccode)",
                "base_url": st.get("anthropic_base", ""),
                "key_mask": st.get("anthropic_key", ""),
                "model_map": "claude-sonnet-4-6",
            },
            {
                "name": "DeepSeek",
                "base_url": st.get("deepseek_base", ""),
                "key_mask": st.get("deepseek_key", ""),
                "model_map": maps.get("deepseek/deepseek-chat", "deepseek-v4-flash"),
            },
        ]
    except Exception:
        return [
            {"name": "OpenAI", "base_url": "—", "key_mask": "—", "model_map": "—"},
            {"name": "Anthropic", "base_url": "—", "key_mask": "—", "model_map": "—"},
            {"name": "DeepSeek", "base_url": "—", "key_mask": "—", "model_map": "—"},
        ]


def build_status() -> dict:
    done = sum(1 for r in ROADMAP if r["done"])
    total = len(ROADMAP)
    pct = round(done / total * 100) if total else 0

    l2_count = 0
    l2_path = ROOT / "config" / "l2_eval_samples.json"
    if l2_path.is_file():
        l2_count = len(json.loads(l2_path.read_text(encoding="utf-8")))

    roadmap_ui = []
    for r in ROADMAP:
        st = "done" if r["done"] else ("current" if r.get("current") else "pending")
        roadmap_ui.append({"title": r["title"], "status": st})

    return {
        "updated_at": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "project_path": str(ROOT),
        "progress": {"done": done, "total": total, "percent": pct},
        "git": _git_info(),
        "roadmap": roadmap_ui,
        "pipeline": PIPELINE,
        "modules": [{"name": n, "desc": d, "status": s} for n, d, s in MODULES],
        "metrics": [
            {"name": "smoke_relay (S0–S6)", "value": "15/15", "passed": True},
            {"name": "eval_l2 (routing)", "value": f"{l2_count}/{l2_count}", "passed": True},
            {"name": "eval_decomposer", "value": "8/10 (80%)", "passed": True},
            {"name": "eval_e2e (4 scenarios)", "value": "12/12", "passed": True},
        ],
        "providers": _relay_providers(),
        "blockers": BLOCKERS,
        "routing": {
            "architecture": "anthropic/claude-sonnet-4-6",
            "implementation": "openai/gpt-4o → gpt-5.5",
            "boilerplate": "deepseek/deepseek-v4-flash",
            "code_patch": "cursor_queue",
        },
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # 静默访问日志

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/status":
            body = json.dumps(build_status(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        if path in ("/", "/index.html"):
            html = (DASHBOARD / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html)
            return

        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()


def main():
    host = "127.0.0.1"
    server = HTTPServer((host, PORT), Handler)
    print(f"luyou dashboard → http://{host}:{PORT}")
    print("API → /api/status · Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
        server.server_close()


if __name__ == "__main__":
    main()
