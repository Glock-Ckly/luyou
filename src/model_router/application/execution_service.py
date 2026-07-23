from __future__ import annotations

import asyncio
import time

from model_router.domain.errors import ProviderError, ProviderInternalError, ProviderTimeout
from model_router.domain.models import (
    AttemptRecord,
    ExecutionEvent,
    ExecutionResult,
    ModelId,
    ModelRequest,
    RetryPolicy,
    TraceId,
)
from model_router.ports.model_provider import ModelProvider
from model_router.application.provider_registry import ProviderRegistry
from model_router.ports.execution_observer import ExecutionObserver, NullExecutionObserver


class ExecutionService:
    def __init__(
        self,
        provider: ModelProvider | None = None,
        retry_policy: RetryPolicy | None = None,
        *,
        registry: ProviderRegistry | None = None,
        observer: ExecutionObserver | None = None,
        timeout_seconds: float = 120.0,
    ):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if provider is None and registry is None:
            raise ValueError("provider or registry is required")
        self.registry = registry or ProviderRegistry(default_provider=provider)
        self.observer = observer or NullExecutionObserver()
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
        unique_candidates = _dedupe(candidates)
        health_cache = {}
        self.observer.record(ExecutionEvent(trace_id, "request_started"))

        for candidate_index, model_id in enumerate(unique_candidates):
            provider_key = model_id.provider_id.value
            if provider_key not in health_cache:
                health_cache[provider_key] = await self.registry.health(model_id.provider_id)
            if not health_cache[provider_key].available:
                attempt = AttemptRecord(
                    model_id=model_id,
                    attempt=0,
                    status="skipped",
                    action="skip_unavailable",
                    latency_ms=0,
                    error_type="provider_unavailable",
                )
                attempts.append(attempt)
                self._record_attempt(trace_id, attempt)
                last_error_type = "provider_unavailable"
                continue

            provider = self.registry.provider_for(model_id)
            for attempt_number in range(1, self.retry_policy.max_retries + 2):
                started = time.perf_counter()
                try:
                    response = await asyncio.wait_for(
                        provider.execute(ModelRequest(model_id, prompt, trace_id)),
                        timeout=self.timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    error: ProviderError = ProviderTimeout("provider attempt timed out")
                except ProviderError as provider_error:
                    error = provider_error
                except Exception as unexpected:
                    error = ProviderInternalError(type(unexpected).__name__)
                else:
                    attempt = AttemptRecord(
                        model_id=model_id,
                        attempt=attempt_number,
                        status="success",
                        action="return_response",
                        latency_ms=_elapsed_ms(started),
                    )
                    attempts.append(attempt)
                    self._record_attempt(trace_id, attempt)
                    return self._finish(ExecutionResult(
                        trace_id=trace_id,
                        outcome="success",
                        response=response,
                        attempts=tuple(attempts),
                    ))

                last_error_type = error.code
                has_retry = error.retryable and attempt_number <= self.retry_policy.max_retries
                has_fallback = error.retryable and candidate_index < len(unique_candidates) - 1
                if has_retry:
                    action = "retry"
                elif has_fallback:
                    action = "fallback"
                else:
                    action = "fail"

                attempt = AttemptRecord(
                    model_id=model_id,
                    attempt=attempt_number,
                    status="failed",
                    action=action,
                    latency_ms=_elapsed_ms(started),
                    error_type=error.code,
                )
                attempts.append(attempt)
                self._record_attempt(trace_id, attempt)

                if has_retry:
                    continue
                if not error.retryable:
                    return self._finish(ExecutionResult(
                        trace_id=trace_id,
                        outcome="failed",
                        response=None,
                        attempts=tuple(attempts),
                        final_error_type=error.code,
                    ))
                break

        return self._finish(ExecutionResult(
            trace_id=trace_id,
            outcome="all_providers_failed",
            response=None,
            attempts=tuple(attempts),
            final_error_type=last_error_type,
        ))

    def _record_attempt(self, trace_id: TraceId, attempt: AttemptRecord) -> None:
        self.observer.record(ExecutionEvent(
            trace_id=trace_id,
            kind="attempt",
            model_id=attempt.model_id,
            status=attempt.status,
            action=attempt.action,
            latency_ms=attempt.latency_ms,
            error_type=attempt.error_type,
        ))

    def _finish(self, result: ExecutionResult) -> ExecutionResult:
        self.observer.record(ExecutionEvent(
            trace_id=result.trace_id,
            kind="request_finished",
            status=result.outcome,
            error_type=result.final_error_type,
        ))
        return result


def _dedupe(candidates: list[ModelId]) -> list[ModelId]:
    return list(dict.fromkeys(candidates))


def _elapsed_ms(started: float) -> int:
    return max(1, round((time.perf_counter() - started) * 1000))
