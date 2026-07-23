from __future__ import annotations

from model_router.domain.errors import ProviderUnavailable
from model_router.domain.models import ModelId, ProviderHealth, ProviderId
from model_router.ports.model_provider import ModelProvider


class ProviderRegistry:
    def __init__(self, default_provider: ModelProvider | None = None):
        self.default_provider = default_provider
        self._providers: dict[str, ModelProvider] = {}

    def register(self, provider_id: str | ProviderId, provider: ModelProvider) -> None:
        key = provider_id.value if isinstance(provider_id, ProviderId) else ProviderId(provider_id).value
        self._providers[key] = provider

    def provider_for(self, model_id: ModelId) -> ModelProvider:
        provider = self._providers.get(model_id.provider_id.value, self.default_provider)
        if provider is None:
            raise ProviderUnavailable(f"provider {model_id.provider_id.value} is not registered")
        return provider

    async def health(self, provider_id: ProviderId) -> ProviderHealth:
        provider = self._providers.get(provider_id.value, self.default_provider)
        if provider is None:
            return ProviderHealth(provider_id, False, "provider is not registered")
        health_method = getattr(provider, "health", None)
        if not callable(health_method):
            return ProviderHealth(provider_id, True, "health check not implemented")
        try:
            return await health_method(provider_id)
        except Exception as error:
            return ProviderHealth(provider_id, False, f"health check failed: {type(error).__name__}")
