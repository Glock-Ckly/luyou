# ExecutionJob Lifecycle

## States

`DRAFT`, `ANALYZING`, `WAITING_APPROVAL`, `READY`, `RUNNING`, `VERIFYING`, `REPAIRING`,
`SUCCEEDED`, `FAILED`, `CANCELLED`.

## Legal transitions

| Current | Next |
|---|---|
| DRAFT | ANALYZING, CANCELLED |
| ANALYZING | WAITING_APPROVAL, READY, FAILED, CANCELLED |
| WAITING_APPROVAL | READY, CANCELLED |
| READY | RUNNING, CANCELLED |
| RUNNING | VERIFYING, FAILED, CANCELLED |
| VERIFYING | SUCCEEDED, REPAIRING, FAILED, CANCELLED |
| REPAIRING | RUNNING, FAILED, CANCELLED |
| SUCCEEDED | none |
| FAILED | none |
| CANCELLED | none |

Any unlisted transition is illegal. Every accepted transition increments `version` and appends a
timestamped event. `READY -> RUNNING` requires approved approval status or automatic approval mode.
`VERIFYING -> SUCCEEDED` requires a persisted VerificationReport with status PASS. Repair requires a
repairable report and remaining attempt, time and cost budgets.

## Aggregate invariants

- `job_id` derives deterministically from the IdempotencyKey; repeated creation returns the same Job.
- Attempt sequence numbers are contiguous and append-only.
- Terminal Jobs reject transitions, attempts, leases and result replacement.
- Cancellation is legal from every non-terminal state and revokes active leases.
- A Job is never successful merely because routing, dispatch, queue insertion or model answering worked.
- Optimistic version checks protect all updates; persistence and HTTP remain adapters.

## Async contract

Future `POST /api/execution/jobs` returns 202 with `job_id`, `state` and query links. Workers claim a
lease, heartbeat it and append receipts. Synchronous `/api/route` remains compatible and does not
create an ExecutionJob unless an explicit job endpoint is used.
