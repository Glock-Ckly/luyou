# Reliability Invariants

1. Use one request-wide Trace ID.
2. Retry only retryable errors and cap attempts with RetryPolicy.
3. Preserve candidate order during fallback.
4. Fail fast on authentication and invalid requests.
5. Skip unavailable Providers before execute.
6. Return all_providers_failed only after every eligible candidate is exhausted.
7. Record every attempt action, error type and latency without recording the full prompt.
8. Count request, success, failure, retry, fallback and Provider latency metrics.
9. Exercise the same ExecutionService from production, tests and reliability demos.
