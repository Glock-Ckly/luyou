# Repository Engineering Rules

## Purpose and runtime

This repository is a Python 3.12 AI model router and task-execution demo. It is not a Java runtime.
The language and modular-monolith decision is recorded in `docs/adr/ADR-001-python-existing-runtime.md`.

## Directory responsibilities

| Path | Responsibility |
|---|---|
| `src/model_router/domain/` | Aggregates, value objects, invariants and domain errors |
| `src/model_router/application/` | Use-case orchestration across domain objects and ports |
| `src/model_router/ports/` | Infrastructure-independent contracts required by the application |
| `src/model_router/adapters/` | HTTP, persistence, Provider and other infrastructure translations |
| `scripts/` | Thin runtime entry points, delivery checks and operational helpers |
| `dashboard/` | Six-page native HTML/CSS/JavaScript user interface |

## Dependency direction

Dependencies point from adapters to application to domain. Domain code must not import application,
adapter, dashboard or script modules. Ports describe needs inward; adapters implement them outward.

## Prohibited changes

- Do not place domain decisions in `scripts/dashboard_server.py`; it only dispatches HTTP requests.
- Provider adapters must not choose routes or rewrite routing policy.
- Planners and prompt compilers must not weaken authentication, work-directory, cost or approval boundaries.
- Do not report a route as execution, a queued item as completion, or a recommended model as enforced binding.

## Required quality gates

```powershell
python -m unittest discover -s tests -v
python scripts/test_dashboard_demo.py
node --check dashboard/assets/app.js
git diff --check
python skills/model-router-delivery/scripts/assess_phase.py --phase <phase-name>
```

Run Provider boundary and reliability audits when those paths change.

## Delivery workflow

Each phase follows specification, DDD boundary review, contract definition, Red tests, a Red-only
commit and push, minimal implementation, regression, secondary assessment, then a Green commit and
immediate push. Every completed phase must add an assessment under `docs/assessment/`.

Use the terminology and truthfulness boundaries in section 8 of
`docs/AI_Model_Router_一体化任务路由_总执行流程与审计清单_2026-07-26.md`.
