---
name: router-reliability-audit
description: Audit AI model router retries, fallbacks, fail-fast errors, Provider health filtering, request-wide Trace IDs, attempt events, and metrics through the production ExecutionService path. Use after reliability changes, before release, when a fallback incident occurs, or when demo behavior may have drifted from production behavior.
---

# Router Reliability Audit

Verify invariants through production use cases and ports. Reject a separate demo-only retry algorithm.

## Workflow

1. Read references/reliability-invariants.md and the execution reliability specification.
2. Trace every public execution entry to ExecutionService.
3. Verify bounded same-model retry, ordered fallback and nonretryable fail-fast behavior.
4. Verify unavailable Providers are skipped before execute.
5. Verify one Trace ID spans routing, attempts, responses and metrics.
6. Verify events omit credentials and full prompts.
7. Run scripts/audit_reliability.py from the repository root.
8. Run the complete deterministic suite and document partial or deferred findings.

## Failure Conditions

- A dashboard or test path implements its own retry loop.
- Authentication or invalid-request errors fall through to another Provider.
- Retry or fallback is unbounded.
- Metrics cannot be correlated by Trace ID.
- A failed attempt returns a raw SDK exception to the client.

## Resources

- Read references/reliability-invariants.md before changing policy.
- Run scripts/audit_reliability.py for deterministic fault scenarios.
