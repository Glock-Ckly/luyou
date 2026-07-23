# ADR-001: Keep Python for the MVP

## Context

The source checklists propose Java 21 and Spring Boot, while the repository already contains a working Python router, classifiers, LiteLLM integration, Codex executor and dashboard.

## Decision

Keep Python 3.12 for the MVP and invest in domain boundaries, contracts and tests before considering a language rewrite.

## Consequences

- Existing working behavior remains reusable.
- Delivery focuses on engineering correctness instead of framework migration.
- Java/Spring Boot is not claimed as implemented.

