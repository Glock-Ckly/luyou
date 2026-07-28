# Phase 17 Assessment - DeepSeek Planning Red Contract

## Scope

- Defined the Planning bounded-context contract for Goal-first task analysis.
- Added the DeepSeek planner prompt template without credentials or environment values.
- Added Red tests for domain invariants, planner transport, Markdown artifacts, HTTP endpoints and UI recovery markers.

## DDD assessment

Planning owns analysis, decomposition, model recommendations and deterministic checklist compilation.
Task owns persistence and lifecycle; Routing owns executable decisions; Provider owns LLM transport;
Verification remains the only authority that can declare acceptance success.

## TDD evidence

- Domain, adapter and HTTP tests fail because implementation modules and routes do not exist.
- The existing authentication test remains Green, proving the new endpoints must preserve the security boundary.
- The dashboard test fails on the expected missing Goal-first controls, removed header and token recovery flow.
- The repository count assertion also fails because Green documentation counts are intentionally not updated in Red.

## Secondary audit

- Red-only boundary: specification, prompt and tests; no production implementation changed.
- Secret scan: no committed API-key-shaped value found.
- Expected Red result: 21 new offline tests and 1 new dashboard test define the implementation contract.

## Follow-up

Implement the minimum domain, ports, adapters, application service, HTTP routes and UI required to
turn these failures Green.

## Commit

Red contract commit: `7cefb98612a82efb831e253bf326003aba614836`.
Application-service Red addendum: recorded by the immediately following Git history entry.
