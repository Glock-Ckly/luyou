#!/usr/bin/env python3
"""luyou 路由分发台 - 本机 http://127.0.0.1:1785"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = ROOT / "dashboard"
PORT = 1785


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
        sys.path.insert(0, str(ROOT / "src"))
        from budget_adapter import get_budget_ratio_sync

        return float(get_budget_ratio_sync())

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_fetch).result(timeout=3.0)
    except Exception:
        return 0.0


def build_meta() -> dict:
    return {
        "project_path": str(ROOT),
        "git": _git_info(),
        "budget_ratio": _budget_ratio(),
    }


def _run_dispatch(prompt: str, workdir: str) -> dict:
    sys.path.insert(0, str(ROOT / "src"))
    from dispatcher import dispatch_prompt

    return asyncio.run(dispatch_prompt(prompt, workdir=workdir))


def _cursor_queue_pending() -> list[dict]:
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from cursor_queue import list_tasks

        return list_tasks("pending")
    except Exception:
        return []


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
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            self._do_get()
        except (ConnectionAbortedError, BrokenPipeError):
            pass

    def do_POST(self):
        try:
            self._do_post()
        except (ConnectionAbortedError, BrokenPipeError):
            pass

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _do_get(self):
        path = urlparse(self.path).path

        if path == "/api/meta":
            self._json_response(200, build_meta())
            return

        if path == "/api/cursor/queue":
            self._json_response(200, {"pending": _cursor_queue_pending()})
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

    def _do_post(self):
        path = urlparse(self.path).path
        if path != "/api/route":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            self._json_response(400, {"error": "invalid JSON"})
            return

        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            self._json_response(400, {"error": "prompt is required"})
            return

        workdir = (body.get("workdir") or str(ROOT)).strip()
        try:
            result = _run_dispatch(prompt, workdir)
            self._json_response(200, result)
        except Exception as e:
            self._json_response(500, {"error": str(e)})


def main():
    host = "127.0.0.1"
    server = HTTPServer((host, PORT), Handler)
    print(f"luyou dashboard -> http://{host}:{PORT}")
    print("API -> GET /api/meta | POST /api/route | GET /api/cursor/queue | Ctrl+C stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
        server.server_close()


if __name__ == "__main__":
    main()
