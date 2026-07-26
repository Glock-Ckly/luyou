# Verification Contract

## Delivery strategies

Five base delivery categories are defined; RELEASE is a composite policy over all applicable checks.

| delivery_type | Required verification |
|---|---|
| ANSWER | non-empty, return schema, no false execution claims, secret scan |
| PLAN | required sections, boundaries, executable criteria, no empty promises |
| PATCH | patch applies, FileScope respected, `git diff --check` |
| REPOSITORY_CHANGE | Red/Green evidence, regression, lint/build, scoped changed files |
| DOCUMENT | file exists, UTF-8, required structure, secret scan, readability |
| RELEASE | all applicable checks, version/status consistency, explicit commit/push authority |

## VerificationReport

Required fields are `status`, `criterion_results`, `commands`, `exit_codes`, `changed_files`,
`forbidden_path_hits`, `secret_scan`, `artifacts`, `repairable` and `evidence_summary`. Status is PASS,
REPAIRABLE_FAILURE or FINAL_FAILURE.

PASS requires all seven conditions: executor success; binding contract satisfied; required Artifacts
exist; every Acceptance Criterion passes; required commands exit zero; no forbidden path changed;
secret scan passes. Model self-assessment is not evidence. Verification cannot alter criteria or run
commands outside the allowlist. Timeout is recorded as failure. Secret leakage and forbidden writes are
final failures; bounded test failures may be repairable.

## Independence

The Verification Context consumes immutable criteria, receipt and artifacts. It does not route,
execute, repair or rewrite the requested scope. A Job reaches SUCCEEDED only after its report is
persisted with PASS.
