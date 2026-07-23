---
name: provider-adapter-contract
description: Add or audit an AI model Provider adapter behind the ModelProvider port with normalized request and response types, health reporting, error mapping, timeout compatibility, and shared contract tests. Use when integrating a new model vendor, relay, SDK, authentication scheme, or provider-specific failure behavior.
---

# Provider Adapter Contract

Keep vendor details at the infrastructure edge and preserve routing-domain independence.

## Workflow

1. Read the ModelProvider port, provider contract specification and error taxonomy.
2. Add contract tests before the adapter implementation.
3. Accept only the normalized ModelRequest and return ModelResponse.
4. Map SDK exceptions to the standard provider errors in references/provider-error-matrix.md.
5. Implement health without selecting models or changing routing policy.
6. Register the adapter through ProviderRegistry rather than editing execution policy.
7. Run scripts/validate_adapter_boundary.py with the adapter path.
8. Run the shared contract suite and full deterministic regression.

## Boundaries

- Never import routing_table, dispatcher or orchestrator from a provider adapter.
- Never retry or select fallback models inside the adapter.
- Never log secrets or raw authentication errors.
- Keep vendor response parsing isolated and normalize missing usage values to zero.

## Resources

- Read references/provider-error-matrix.md when mapping failures.
- Run scripts/validate_adapter_boundary.py before assessment.
