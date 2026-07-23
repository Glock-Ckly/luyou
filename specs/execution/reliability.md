# Retry, Fallback and Timeout Specification

## Retry

Retry repeats the same provider/model for transient errors only. Default: one retry, bounded by policy.

## Fallback

Fallback selects the next ordered candidate after retries are exhausted or the provider is unavailable.

## Timeout

Every provider attempt has an explicit timeout. Timeout maps to ProviderTimeout and participates in retry/fallback policy.

## Final failure

If all candidates fail, return AllProvidersFailed with trace ID and sanitized attempt summaries. Never return raw exception strings to external clients.

