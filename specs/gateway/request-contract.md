# Gateway Request Contract

## OpenAI-compatible endpoint

POST /v1/chat/completions accepts model and a non-empty messages array. Supported roles are system, user and assistant. The Gateway converts messages into one normalized prompt and delegates to the public route-and-execute use case.

The response includes chat.completion shape, actual selected model, assistant content, zero-valued usage when aggregation is unavailable, and router_trace_id.

## Native demo endpoint

POST /api/route accepts prompt and optional workdir. Workdir must resolve inside MODEL_ROUTER_ALLOWED_WORKDIRS.

## Error contract

Errors use error.code, error.message and error.type. Internal exceptions and Provider SDK details must not cross the HTTP boundary.
