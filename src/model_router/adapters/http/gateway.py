from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class GatewayRequestError(ValueError):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@dataclass(frozen=True)
class GatewayConfig:
    api_token: str = ""
    allowed_workdirs: tuple[Path, ...] = ()
    allowed_origins: tuple[str, ...] = (
        "http://127.0.0.1:1785",
        "http://localhost:1785",
    )

    @classmethod
    def from_env(cls, root: Path) -> "GatewayConfig":
        raw_workdirs = os.environ.get("MODEL_ROUTER_ALLOWED_WORKDIRS", str(root))
        workdirs = tuple(
            Path(item.strip()).resolve()
            for item in raw_workdirs.split(os.pathsep)
            if item.strip()
        )
        raw_origins = os.environ.get(
            "MODEL_ROUTER_ALLOWED_ORIGINS",
            "http://127.0.0.1:1785,http://localhost:1785",
        )
        origins = tuple(item.strip() for item in raw_origins.split(",") if item.strip())
        return cls(
            api_token=os.environ.get("MODEL_ROUTER_API_TOKEN", "").strip(),
            allowed_workdirs=workdirs or (root.resolve(),),
            allowed_origins=origins,
        )


def authorize(headers: Mapping[str, str], config: GatewayConfig) -> None:
    if not config.api_token:
        return
    authorization = headers.get("Authorization", "")
    if authorization != f"Bearer {config.api_token}":
        raise GatewayRequestError(401, "invalid_api_key", "Invalid or missing API token")


def allowed_origin(origin: str | None, config: GatewayConfig) -> str | None:
    if origin and origin in config.allowed_origins:
        return origin
    return None


def resolve_workdir(value: str | None, config: GatewayConfig) -> Path:
    if not config.allowed_workdirs:
        raise GatewayRequestError(500, "gateway_misconfigured", "No work directory is configured")
    candidate = Path(value).resolve() if value else config.allowed_workdirs[0]
    for allowed in config.allowed_workdirs:
        try:
            candidate.relative_to(allowed.resolve())
            return candidate
        except ValueError:
            continue
    raise GatewayRequestError(403, "workdir_forbidden", "Work directory is outside allowed roots")


def parse_chat_completion(body: dict) -> tuple[str, str]:
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise GatewayRequestError(400, "invalid_request", "messages must be a non-empty array")
    lines: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            raise GatewayRequestError(400, "invalid_request", "each message must be an object")
        role = message.get("role")
        content = message.get("content")
        if role not in {"system", "user", "assistant"} or not isinstance(content, str):
            raise GatewayRequestError(400, "invalid_request", "message role or content is invalid")
        if content.strip():
            lines.append(f"{role}: {content.strip()}")
    if not lines:
        raise GatewayRequestError(400, "invalid_request", "messages contain no text")
    model = body.get("model") or "router/auto"
    if not isinstance(model, str):
        raise GatewayRequestError(400, "invalid_request", "model must be a string")
    return "\n".join(lines), model


def format_chat_completion(result: dict, *, requested_model: str) -> dict:
    trace_id = str(result.get("trace_id") or "tr_unknown")
    selected_model = str(result.get("selected_model") or requested_model)
    return {
        "id": f"chatcmpl-{trace_id.removeprefix('tr_')}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": selected_model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": str(result.get("result") or "")},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "router_trace_id": trace_id,
    }


def safe_error_payload(error: Exception) -> tuple[int, dict]:
    if isinstance(error, GatewayRequestError):
        status = error.status
        code = error.code
        message = error.message
    else:
        status = 500
        code = "internal_error"
        message = "The router could not complete the request"
    return status, {"error": {"code": code, "message": message, "type": "router_error"}}
