from typing import Protocol

from model_router.domain.models import ModelRequest, ModelResponse, ProviderHealth, ProviderId


class ModelProvider(Protocol):
    async def execute(self, request: ModelRequest) -> ModelResponse:
        ...

    async def health(self, provider_id: ProviderId) -> ProviderHealth:
        ...

