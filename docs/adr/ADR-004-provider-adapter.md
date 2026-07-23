# ADR-004: Provider Access Through a Port

## Decision

Application and domain code depend on ModelProvider, never directly on LiteLLM. LiteLLM is one adapter. Tests use deterministic fake adapters.

## Consequences

- New providers do not modify routing rules.
- Provider contract tests become reusable.
- Error mapping is centralized at adapter boundaries.

