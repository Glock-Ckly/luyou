# Acceptance Criteria

## Core request

1. Given a valid request, the gateway returns a normalized response and trace ID.
2. The routing decision records task type, complexity, primary model, fallback chain and budget zone.
3. The application layer depends on ports, not LiteLLM, Codex or filesystem implementations.

## Reliability

1. A retryable provider error retries within the configured per-model limit.
2. Exhausted retryable errors advance to the next model.
3. Authentication and validation errors fail fast.
4. All-provider failure returns a normalized error without leaking credentials or SDK internals.
5. Reliability Lab invokes the same production use case with a fault-injecting provider.

## Provider contract

Every provider adapter must accept ModelRequest, return ModelResponse, preserve provider/model identity and usage, respect timeout/cancellation, map errors into standard provider errors and pass the shared contract suite.

## Observability

- One trace ID spans gateway, routing and provider attempts.
- Each provider attempt records latency, outcome and error type.
- Metrics expose request, failure, retry and fallback counts.
- Sensitive request credentials are never logged.

## Quality gates

- Standard test discovery succeeds.
- Unit tests are deterministic and offline.
- Provider integration/evaluation tests are separately marked.
- All modified behavior has a failing test before implementation.
- Each implementation phase updates the assessment report before commit and push.

