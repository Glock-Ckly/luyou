from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderId:
    value: str

    def __post_init__(self):
        value = self.value.strip()
        if not value or "/" in value:
            raise ValueError("provider id must be a non-empty segment")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True)
class ModelId:
    provider_id: ProviderId
    name: str

    def __post_init__(self):
        name = self.name.strip()
        if not name or "/" in name:
            raise ValueError("model name must be a non-empty segment")
        object.__setattr__(self, "name", name)

    @property
    def value(self) -> str:
        return f"{self.provider_id.value}/{self.name}"

    @classmethod
    def parse(cls, value: str) -> ModelId:
        provider, separator, name = value.strip().partition("/")
        if not separator:
            raise ValueError("model id must use provider/model format")
        return cls(provider_id=ProviderId(provider), name=name)


@dataclass(frozen=True)
class TraceId:
    value: str

    def __post_init__(self):
        if not self.value.strip():
            raise ValueError("trace id is required")

    @classmethod
    def new(cls) -> TraceId:
        return cls(f"tr_{uuid.uuid4().hex[:16]}")


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class ModelRequest:
    model_id: ModelId
    prompt: str
    trace_id: TraceId


@dataclass(frozen=True)
class ModelResponse:
    model_id: ModelId
    content: str
    usage: Usage = field(default_factory=Usage)


@dataclass(frozen=True)
class ProviderHealth:
    provider_id: ProviderId
    available: bool
    detail: str = ""


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 1

    def __post_init__(self):
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")


@dataclass(frozen=True)
class AttemptRecord:
    model_id: ModelId
    attempt: int
    status: str
    action: str
    latency_ms: int
    error_type: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    trace_id: TraceId
    outcome: str
    response: ModelResponse | None
    attempts: tuple[AttemptRecord, ...]
    final_error_type: str | None = None

    @property
    def selected_model(self) -> ModelId | None:
        return self.response.model_id if self.response else None

