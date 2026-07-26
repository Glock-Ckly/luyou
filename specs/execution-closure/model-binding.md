# Model Binding and ExecutionReceipt

## Binding modes

- `ENFORCED`: argv, configuration and response evidence prove the required model was used.
- `VERIFIED_FALLBACK`: the actual model is in the approved fallback list and `fallback_reason` is present.
- `EXECUTOR_MANAGED`: the executor controls model selection; UI and reports must not claim enforcement.

Writing a model name into a prompt is never binding evidence. Codex and Cursor remain
`EXECUTOR_MANAGED` until their invocation and result contracts prove actual-model selection.

## ExecutionReceipt

The 11 logical required groups serialize `started_at` and `completed_at` separately:

1. `requested_model`
2. `actual_model`
3. `binding_mode`
4. `binding_status`
5. `executor_id`
6. `executor_version`
7. `fallback_reason`
8. `input_tokens`
9. `output_tokens`
10. `actual_cost_usd`
11. `started_at` plus `completed_at`

Repository execution additionally requires `changed_files`, `exit_codes`, `commands_run`,
`final_message` and `artifact_ids`. Missing required evidence invalidates the receipt. Fallback must
name its reason; EXECUTOR_MANAGED may not return an `enforced` status.

## Executor capabilities

| Executor | Delivery | Repository | Commands | Binding |
|---|---|---|---|---|
| ProviderAnswerExecutor | ANSWER, DOCUMENT | no | no | ENFORCED or VERIFIED_FALLBACK |
| CodexRepositoryExecutor | PATCH, REPOSITORY_CHANGE | scoped | allowlist | EXECUTOR_MANAGED until proven |
| CursorWorkerExecutor | PATCH, FILE_EDIT | scoped worker | worker policy | EXECUTOR_MANAGED |
| DocumentExecutor | DOCUMENT | artifacts only | no | local code |

Queue acceptance is dispatch success only. Job success requires a valid receipt followed by PASS verification.
