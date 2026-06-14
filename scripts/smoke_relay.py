#!/usr/bin/env python3
"""Ccode 中转站分阶段 smoke test（S0–S6）。任一步 401/404 即停并报告。"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from relay_config import apply_relay_env, get_relay_status, resolve_model  # noqa: E402

PASSED = 0
FAILED = 0
RESULTS: list[str] = []


def ok(name: str, cond: bool, detail: str = "") -> bool:
    global PASSED, FAILED
    line = f"{'PASS' if cond else 'FAIL'}: {name}" + (f" — {detail}" if detail else "")
    print(line)
    RESULTS.append(line)
    if cond:
        PASSED += 1
    else:
        FAILED += 1
    return cond


def stop(msg: str) -> None:
    print(f"\nSTOP: {msg}")
    sys.exit(1)


def fetch_models(base: str, api_key: str, auth_header: str = "Bearer") -> tuple[int, str]:
    """GET {base}/v1/models（base 可含或不含 /v1）。"""
    base = base.rstrip("/")
    if base.endswith("/v1"):
        url = f"{base}/models"
    else:
        url = f"{base}/v1/models"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"{auth_header} {api_key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")[:500]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        return e.code, body
    except Exception as e:
        return -1, str(e)


async def call_one(model: str, prompt: str = "Reply with exactly: OK") -> tuple[bool, str]:
    from relay_llm import call_llm

    try:
        resp = await call_llm(
            model=resolve_model(model),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=64,
        )
        text = (resp.content or "").strip()
        return bool(text), text[:200]
    except Exception as e:
        return False, str(e)[:300]


def s0_env() -> None:
    apply_relay_env()
    st = get_relay_status()
    ok("S0 openai_base set", bool(st["openai_base"]), st["openai_base"])
    ok("S0 anthropic_base set", bool(st["anthropic_base"]), st["anthropic_base"])
    ok("S0 deepseek_base set", bool(st["deepseek_base"]), st["deepseek_base"])
    ok("S0 openai_key set", st["openai_key"] != "(missing)", st["openai_key"])
    ok("S0 anthropic_key set", st["anthropic_key"] != "(missing)", st["anthropic_key"])
    ok("S0 deepseek_key set", st["deepseek_key"] != "(missing)", st["deepseek_key"])


def s1_models() -> None:
    providers = [
        ("openai", os.environ.get("OPENAI_API_BASE", ""), os.environ.get("OPENAI_API_KEY", "")),
        ("anthropic", os.environ.get("ANTHROPIC_API_BASE", ""), os.environ.get("ANTHROPIC_API_KEY", "")),
        ("deepseek", os.environ.get("DEEPSEEK_API_BASE", ""), os.environ.get("DEEPSEEK_API_KEY", "")),
    ]
    for name, base, key in providers:
        if not base or not key:
            if not ok(f"S1 {name} models", False, "missing base or key"):
                stop(f"S1 {name}: missing base or key")
            continue
        code, body = fetch_models(base, key)
        if code in (401, 403, 404):
            stop(f"S1 {name} models HTTP {code}: {body}")
        ok(f"S1 {name} models HTTP {code}", code == 200, body[:120].replace("\n", " "))


async def s2_s4_llm() -> None:
    tests = [
        ("S2 deepseek", "deepseek/deepseek-chat"),
        ("S3 openai", "openai/gpt-4o"),
        ("S4 anthropic", "anthropic/claude-sonnet-4-6"),
    ]
    for label, model in tests:
        success, detail = await call_one(model)
        if not success and any(x in detail.lower() for x in ("401", "403", "authentication", "invalid api key")):
            stop(f"{label} auth error: {detail}")
        if not ok(label, success, detail):
            print(f"  (non-auth failure — check model mapping in config/relay_models.yaml)")


def s5_l1() -> None:
    proc = subprocess.run(
        [sys.executable, str(SRC / "l1_classifier.py")],
        cwd=str(SRC),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    ok("S5 L1 self-test exit 0", proc.returncode == 0, out.strip()[-200:] if out else "no output")


async def s6_e2e() -> None:
    from orchestrator import handle_prompt

    result = await handle_prompt("写一个 hello world 函数，只输出代码")
    model = result.get("selected_model", "")
    text = result.get("result", "")
    ok("S6 selected_model not none", model not in ("", "none"), model)
    ok("S6 result not ERROR", "[ERROR]" not in text and "All models failed" not in text, text[:150].replace("\n", " "))


async def main() -> None:
    print("=== Smoke Relay S0–S6 ===\n")
    s0_env()
    print()
    s1_models()
    print()
    await s2_s4_llm()
    print()
    s5_l1()
    print()
    await s6_e2e()
    print(f"\n=== Done: {PASSED} passed, {FAILED} failed ===")
    if FAILED > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
