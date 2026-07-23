from __future__ import annotations

import asyncio
import time

from model_router.domain.errors import ProviderError, ProviderInternalError, ProviderTimeout
from model_router.domain.models import (
    AttemptRecord,
    ExecutionResult,
    ModelId,
    ModelRequest,
    RetryPolicy,
    TraceId,
)
from model_router.ports.model_provider import ModelProvider


class ExecutionService:
    def __init__(
        self,
        provider: ModelProvider,
        retry_policy: RetryPolicy | None = None,
        *,
        timeout_seconds: float = 120.0,
    ):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.provider = provider
        self.retry_policy = retry_policy or RetryPolicy()
        self.timeout_seconds = timeout_seconds

    async def execute(
        self,
        *,
        trace_id: TraceId,
        prompt: str,
        candidates: list[ModelId],
    ) -> ExecutionResult:
        if not candidates:
            raise ValueError("at least one model candidate is required")

        attempts: list[AttemptRecord] = []
        last_error_type: str | None = None

        for candidate_index, model_id in enumerate(_dedupe(candidates)):
            for attempt_number in range(1, self.retry_policy.max_retries + 2):
                started = time.perf_counter()
                try:
                    response = await asyncio.wait_for(
                        self.provider.execute(ModelRequest(model_id, prompt, trace_id)),
                        timeout=self.timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    error: ProviderError = ProviderTimeout("provider attempt timed out")
                except ProviderError as provider_error:
                    error = provider_error
                except Exception as unexpected:
                    error = ProviderInternalError(type(unexpected).__name__)
                else:
                    attempts.append(
                        AttemptRecord(
                            model_id=model_id,
                            attempt=attempt_number,
                            status="success",
                            action="return_response",
                            latency_ms=_elapsed_ms(started),
                        )
                    )
                    return ExecutionResult(
                        trace_id=trace_id,
                        outcome="success",
                        response=response,
                        attempts=tuple(attempts),
                    )

                last_error_type = error.code
                has_retry = error.retryable and attempt_number <= self.retry_policy.max_retries
                has_fallback = error.retryable and candidate_index < len(_dedupe(candidates)) - 1
                if has_retry:
                    action = "retry"
                elif has_fallback:
                    action = "fallback"
                else:
                    action = "fail"

                attempts.append(
                    AttemptRecord(
                        model_id=model_id,
                        attempt=attempt_number,
                        status="failed",
                        action=action,
                        latency_ms=_elapsed_ms(started),
                        error_type=error.code,
                    )
                )

                if has_retry:
                    continue
                if not error.retryable:
                    return ExecutionResult(
                        trace_id=trace_id,
                        outcome="failed",
                        response=None,
                        attempts=tuple(attempts),
                        final_error_type=error.code,
                    )
                break

        return ExecutionResult(
            trace_id=trace_id,
            outcome="all_providers_failed",
            response=None,
            attempts=tuple(attempts),
            final_error_type=last_error_type,
        )


def _dedupe(candidates: list[ModelId]) -> list[ModelId]:
    return list(dict.fromkeys(candidates))


def _elapsed_ms(started: float) -> int:
    return max(1, round((time.perf_counter() - started) * 1000))

