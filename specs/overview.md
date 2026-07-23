# AI Model Router System Specification

## Goal

Build a unified AI model gateway that accepts a stable external request contract, selects a model from deterministic domain policies, executes through provider ports, applies bounded retry/fallback, and returns a normalized response with one trace ID.

## Existing-runtime decision

The repository is Python-based and already has working routing, classifiers, LiteLLM integration, Codex execution and a dashboard. The project therefore keeps Python for the MVP instead of rewriting into Java/Spring Boot. This is an explicit ADR, not an accidental deviation.

## System boundary

HTTP Client -> Gateway Adapter -> RouteAndExecute Use Case -> Routing Domain -> Execution Domain -> ModelProvider Port -> Provider Adapter.

The modular monolith must preserve a future HTTP Gateway -> gRPC -> Routing Service -> Provider Adapter boundary.

## MVP capabilities

- OpenAI-compatible chat-completion endpoint.
- Deterministic task/complexity/budget routing.
- Provider abstraction and registry.
- Standard provider errors.
- Timeout, retry and fallback policies.
- Trace ID, structured events and in-memory metrics.
- Unit, integration, contract and end-to-end tests.
- Docker packaging and health endpoint.
- Five-page operational demo backed by the production use case.

## Deferred capabilities

- Persistent billing and distributed runtime state.
- Production-grade multi-tenancy and authorization.
- Kubernetes and distributed tracing backend.
- Agent-assisted routing in the synchronous reliability path.

Deferred capabilities must have ADRs and must not be presented as implemented.

