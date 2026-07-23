from __future__ import annotations

from collections.abc import Awaitable, Callable

from model_router.domain.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderInternalError,
    ProviderRateLimited,
    ProviderRequestInvalid,
    ProviderTimeout,
    ProviderUnavailable,
)
from model_router.domain.models import (
    ModelId,
    ModelRequest,
    ModelResponse,
    ProviderHealth,
    ProviderId,
    Usage,
)

ProviderCall = Callable[..., Awaitable[object]]


class LiteLLMProvider:
    def __init__(self, *, call: ProviderCall | None = None):
        self._call = call

    async def execute(self, request: ModelRequest) -> ModelResponse:
        call = self._call or _default_call
        try:
            response = await call(
                model=request.model_id.value,
                messages=[{"role": "user", "content": request.prompt}],
                temperature=0.0,
                max_tokens=4096,
            )
        except Exception as error:
            raise map_provider_error(error) from error

        response_model = str(getattr(response, "model", "") or request.model_id.value)
        try:
            model_id = ModelId.parse(response_model)
        except ValueError:
            model_id = request.model_id
        return ModelResponse(
            model_id=model_id,
            content=str(getattr(response, "content", "")),
            usage=Usage(
                input_tokens=int(getattr(response, "input_tokens", 0) or 0),
                output_tokens=int(getattr(response, "output_tokens", 0) or 0),
                cost_usd=float(getattr(response, "cost_usd", 0.0) or 0.0),
            ),
        )

    async def health(self, provider_id: ProviderId) -> ProviderHealth:
        return ProviderHealth(
            provider_id=provider_id,
            available=True,
            detail="adapter configured",
        )


async def _default_call(**kwargs):
    from relay_llm import call_llm

    return await call_llm(**kwargs)


def map_provider_error(error: Exception) -> ProviderError:
    if isinstance(error, ProviderError):
        return error

    name = type(error).__name__.lower()
    status = getattr(error, "status_code", None)

    if isinstance(error, TimeoutError) or "timeout" in name:
        return ProviderTimeout("provider timed out")
    if status in {401, 403} or "authentication" in name or "permission" in name:
        return ProviderAuthenticationError("provider authentication failed")
    if status == 429 or "ratelimit" in name or "rate_limit" in name:
        return ProviderRateLimited("provider rate limited")
    if status in {400, 404, 409, 422} or "badrequest" in name or "invalidrequest" in name:
        return ProviderRequestInvalid("provider rejected request")
    if status in {502, 503, 504} or any(token in name for token in ("connection", "unavailable", "service")):
        return ProviderUnavailable("provider unavailable")
    return ProviderInternalError("provider internal error")
