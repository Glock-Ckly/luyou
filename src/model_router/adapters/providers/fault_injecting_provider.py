from __future__ import annotations

from model_router.domain.errors import (
    ProviderAuthenticationError,
    ProviderRateLimited,
    ProviderTimeout,
    ProviderUnavailable,
)
from model_router.domain.models import ModelRequest, ModelResponse, ProviderHealth, ProviderId


class FaultInjectingProvider:
    def __init__(self, *, failed_models: set[str], failure_mode: str):
        supported = {"provider_unavailable", "timeout", "rate_limit", "authentication"}
        if failure_mode not in supported:
            raise ValueError("unsupported failure_mode")
        self.failed_models = set(failed_models)
        self.failure_mode = failure_mode

    async def execute(self, request: ModelRequest) -> ModelResponse:
        if request.model_id.value in self.failed_models:
            raise self._failure()
        return ModelResponse(
            model_id=request.model_id,
            content=f"simulated success from {request.model_id.value}",
        )

    async def health(self, provider_id: ProviderId) -> ProviderHealth:
        return ProviderHealth(provider_id=provider_id, available=True, detail="fault simulation adapter")

    def _failure(self):
        errors = {
            "provider_unavailable": ProviderUnavailable("simulated unavailable"),
            "timeout": ProviderTimeout("simulated timeout"),
            "rate_limit": ProviderRateLimited("simulated rate limit"),
            "authentication": ProviderAuthenticationError("simulated authentication error"),
        }
        return errors[self.failure_mode]

