# Cost Ledger Contract

## Entries

Each immutable entry records `ledger_entry_id`, `job_id`, `subtask_id`, `attempt_id`, `executor_id`,
`provider`, `requested_model`, `actual_model`, input/output tokens, estimated and actual USD cost,
currency, price catalog version, entry type, occurred_at and receipt reference.

Entry types are RESERVATION, ACTUAL, RELEASE and ADJUSTMENT. Actual values come from receipts or an
explicitly versioned price calculation; unavailable budget pressure is `unknown`, never silently 0.0.

## Reservation semantics

Before dispatch, reserve the attempt estimate atomically against per-job `max_cost_usd`. Available
budget decreases immediately. Completion posts ACTUAL and releases the unused reservation; failure or
cancellation releases unspent amounts. Duplicate idempotency keys cannot reserve twice. New attempts,
fallbacks and repairs are rejected when projected cost exceeds the remaining hard limit.

## Aggregation and boundaries

Job cost equals immutable ACTUAL entries plus adjustments and can be grouped by subtask, model and
executor. Cost is an input to Routing but this ledger never selects a model. Provider quota snapshots
include source and timestamp and expire explicitly. Persistence is behind a CostLedger Port so SQLite
can later be replaced without changing accounting invariants.
