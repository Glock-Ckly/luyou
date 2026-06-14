"""
Ccode 中转站环境配置 — 加载 ~/.llm-router/.env 并注入 LiteLLM 环境变量。

不改 llm-router 源码；在 orchestrator 导入 call_llm 之前调用 apply_relay_env()。
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

_APPLIED = False
_ENV_PATH = Path.home() / ".llm-router" / ".env"
_MODEL_MAP_PATH = Path(__file__).resolve().parent.parent / "config" / "relay_models.yaml"
_MODEL_MAP: dict[str, str] = {}


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _set_if_present(key: str, value: str) -> None:
    if value:
        os.environ[key] = value


def _load_model_map() -> dict[str, str]:
    global _MODEL_MAP
    if _MODEL_MAP:
        return _MODEL_MAP
    if not _MODEL_MAP_PATH.is_file():
        _MODEL_MAP = {}
        return _MODEL_MAP
    try:
        data = yaml.safe_load(_MODEL_MAP_PATH.read_text(encoding="utf-8")) or {}
        _MODEL_MAP = {str(k): str(v) for k, v in (data.get("models") or {}).items()}
    except Exception:
        _MODEL_MAP = {}
    return _MODEL_MAP


def resolve_model(litellm_model: str) -> str:
    """将路由表模型名映射为中转站实际模型名（若配置了 relay_models.yaml）。"""
    return _load_model_map().get(litellm_model, litellm_model)


def apply_relay_env(env_path: Path | None = None) -> None:
    """加载中转站 .env 并写入 LiteLLM 所需环境变量（幂等）。"""
    global _APPLIED
    if _APPLIED:
        return

    path = env_path or _ENV_PATH
    env = _parse_env_file(path)

    openai_key = env.get("OPENAI_API_KEY", "")
    anthropic_key = env.get("ANTHROPIC_API_KEY", "")
    deepseek_key = env.get("DEEPSEEK_API_KEY", "")

    openai_base = env.get("RELAY_OPENAI_BASE_URL", "")
    anthropic_base = env.get("RELAY_ANTHROPIC_BASE_URL", "")
    deepseek_base = env.get("RELAY_DEEPSEEK_BASE_URL", "")

    _set_if_present("OPENAI_API_KEY", openai_key)
    _set_if_present("ANTHROPIC_API_KEY", anthropic_key)
    _set_if_present("DEEPSEEK_API_KEY", deepseek_key)

    _set_if_present("OPENAI_API_BASE", openai_base)
    _set_if_present("ANTHROPIC_API_BASE", anthropic_base)
    # LiteLLM 同时识别 ANTHROPIC_BASE_URL
    _set_if_present("ANTHROPIC_BASE_URL", anthropic_base)
    _set_if_present("DEEPSEEK_API_BASE", deepseek_base)

    os.environ["LLM_ROUTER_CLAUDE_SUBSCRIPTION"] = "false"

    _load_model_map()
    _APPLIED = True


def _mask_key(key: str) -> str:
    if not key:
        return "(missing)"
    if len(key) <= 8:
        return "****"
    return f"****{key[-4:]}"


def get_relay_status() -> dict[str, str]:
    """返回脱敏后的中转站配置状态（用于 smoke / 调试）。"""
    apply_relay_env()
    return {
        "env_file": str(_ENV_PATH),
        "openai_base": os.environ.get("OPENAI_API_BASE", ""),
        "anthropic_base": os.environ.get("ANTHROPIC_API_BASE", ""),
        "deepseek_base": os.environ.get("DEEPSEEK_API_BASE", ""),
        "openai_key": _mask_key(os.environ.get("OPENAI_API_KEY", "")),
        "anthropic_key": _mask_key(os.environ.get("ANTHROPIC_API_KEY", "")),
        "deepseek_key": _mask_key(os.environ.get("DEEPSEEK_API_KEY", "")),
        "model_map_count": str(len(_load_model_map())),
    }
