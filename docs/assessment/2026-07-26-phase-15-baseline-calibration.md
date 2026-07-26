# Phase 15 Assessment - Baseline Calibration

## Scope completed

- Synchronized the governing checklist with observed repository behavior instead of manufacturing
  failures for behavior that already passed.
- Added strict collection-shape, version, task-status transition and atomic-delete contracts.
- Added 13 acceptance tests: 10 Red tests for missing behavior and 3 Characterization tests for
  existing delete and legal-transition behavior.
- Synchronized README, STATUS and checklist matrix with the six-page, 52 plus 9 deterministic baseline.
- Added root `AGENTS.md` with directory ownership, dependency direction, prohibited changes, quality
  gates, delivery workflow and terminology boundaries.

## TDD evidence

### Governance calibration

The original checklist incorrectly described all ten original entries as failing. Baseline inspection
and a live DELETE probe showed that unknown-task deletion already returned 404, protected-task
deletion already returned 409 and preserved its row, and all legal transitions were accepted because
there was no transition guard. The checklist was corrected to 10 genuine Red tests plus 3 explicit
Characterization tests. Governance commit `b5cada4` was audited and pushed before Phase 15 began.

### Red

Red-only commit: `ff6fbae`.

- Focused domain, HTTP and repository run: 21 tests, 7 failures and 2 errors.
- Dashboard run after correcting one mistaken title expectation: 9 tests, 1 expected failure.
- Total expected Red evidence: 10 failures/errors.
- Characterization evidence remained green: running-task delete returned 409 and preserved the row,
  unknown-task delete returned 404, and every legal transition sample passed.
- The Red-only commit changed one specification and four test files; no production file was present.

### Green

- Focused domain, HTTP and repository run: 21/21 passed.
- Full unit, contract and integration suite: 52/52 passed.
- Dashboard artifact, runtime and documentation suite: 9/9 passed.
- `node --check dashboard/assets/app.js`: passed.
- `git diff --check`: passed.
- `assess_phase.py --phase phase-15-baseline-calibration`: `passed=true`.

## Manual API evidence

The R0-1 through R0-7 HTTP cases were rerun against a separate server on port 1790 with a temporary
SQLite database. The temporary process and database were removed after verification.

| Case | Result |
|---|---|
| R0-1 non-numeric version | 400, `invalid_task` |
| R0-2 fractional version | 400 |
| R0-3 string tags | 400 |
| R0-4 string technology stack | 400 |
| R0-5 mapping acceptance criteria | 400 |
| R0-6 delete running task | 409; subsequent GET 200 |
| R0-7 delete unknown task | 404 |

## DDD assessment

- `ExecutionTask` owns collection normalization and lifecycle transition invariants.
- `TaskService` validates the optimistic-lock contract and coordinates use cases without SQL or HTTP
  response decisions.
- `TaskRepository` exposes the atomic delete condition required by the application.
- `SQLiteTaskRepository` implements the condition with one guarded DELETE and distinguishes not-found
  from lifecycle conflict in the same transaction.
- The HTTP error mapper continues to translate domain validation, not-found and conflict errors to
  400, 404 and 409 respectively.
- Routing data, Dispatcher and Provider adapters were not changed.

The repository instructions prefer CodeGraph for structural analysis, but no `codegraph_*` tools were
available in this session. The secondary boundary review therefore used the constrained production
diff, imports and focused contract tests. This limitation did not affect the executable test evidence.

## Contract and concurrency assessment

- HTTP collection fields require JSON arrays; domain hydration accepts list, tuple or set and rejects
  string, bytes and mappings.
- Supplied versions require a non-boolean integer and must match the current version.
- Status updates follow the specified transition matrix; terminal statuses have no outgoing transitions.
- Protected-status deletion is no longer a service-level read followed by an unconditional delete.
- A zero-row guarded delete performs a same-transaction existence check: missing rows raise
  `TaskNotFound`; existing protected rows raise `TaskConflict` and remain persisted.

## Truthfulness and documentation assessment

- README, STATUS and checklist matrix report six pages, 52/52 offline tests and 9/9 Dashboard checks.
- Historical browser evidence remains attributed to its original phases; no new browser E2E claim was added.
- Task CRUD is not described as a persistent ExecutionJob or completed task-execution loop.
- A route remains a candidate decision, Cursor queue remains queued work, and recommended model text
  is not described as enforced model binding.

## Secondary audit

- Allowed-path review: passed; all implementation files are inside the Phase 15 boundary.
- Forbidden-path review: passed; routing tables, Dispatcher and Provider adapters are unchanged.
- Dependency direction review: passed; adapter to application to domain direction is preserved.
- Regression review: passed; 52/52 plus 9/9 with no skipped or weakened assertions.
- Security review: no authentication, work-directory, Provider credential or prompt boundary changed.
- Documentation overclaim review: passed.

## Residual risks and non-goals

- No parallel multi-connection stress test was added; atomicity is evidenced by SQL shape, transaction
  scope and protected-row integration tests.
- The live server on port 1785 must be restarted to load this commit after delivery.
- ExecutionJob, PromptPackage, model binding, automatic execution, verification and bounded repair
  remain future phases and are not claimed complete.
- Phase 16 must not begin until the Green commit containing this assessment is present on `origin/main`.

## Result

Phase 15 meets its corrected Definition of Done. The Green implementation commit is the commit that
contains this assessment; its resolved hash is recorded in Git history and the task completion report.
