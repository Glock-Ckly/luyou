# Provider Adapter Agent

## Mission

Implement one Provider behind ModelProvider and the shared contract suite.

## Allowed writes

- src/model_router/adapters/providers/
- Provider contract tests
- Provider-specific configuration examples without credentials

## Forbidden

- Do not import or edit routing policy, Dispatcher or Orchestrator.
- Do not implement retry or fallback inside the adapter.
- Do not expose raw SDK errors or credentials.

## Exit criteria

Pass the adapter boundary validator, shared contract tests and normalized error matrix.
