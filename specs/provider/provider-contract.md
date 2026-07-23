# Provider Contract

## Port

ModelProvider exposes async execute(ModelRequest) -> ModelResponse and async health() -> ProviderHealth.

## Standard errors

- ProviderTimeout: retryable
- ProviderRateLimited: retryable
- ProviderUnavailable: retryable/fallback
- ProviderAuthenticationError: fail fast
- ProviderRequestInvalid: fail fast
- ProviderInternalError: policy-controlled retry

Adapters must not select fallback models or change routing policy.

