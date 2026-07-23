class ProviderError(Exception):
    code = "provider_error"
    retryable = False


class ProviderTimeout(ProviderError):
    code = "provider_timeout"
    retryable = True


class ProviderRateLimited(ProviderError):
    code = "provider_rate_limited"
    retryable = True


class ProviderUnavailable(ProviderError):
    code = "provider_unavailable"
    retryable = True


class ProviderInternalError(ProviderError):
    code = "provider_internal"
    retryable = True


class ProviderAuthenticationError(ProviderError):
    code = "provider_authentication"


class ProviderRequestInvalid(ProviderError):
    code = "provider_request_invalid"

