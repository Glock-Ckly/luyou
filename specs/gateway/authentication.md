# Gateway Authentication Specification

## Contract

- Expose health without authentication.
- Require Authorization: Bearer TOKEN for API endpoints when MODEL_ROUTER_API_TOKEN is configured.
- Return a normalized 401 invalid_api_key error for missing or invalid credentials.
- Never forward the gateway token to Provider adapters.
- Never include tokens in events, responses or repository files.

## Rate limit

- Apply a configurable per-client sliding-window limit after authentication.
- Return normalized 429 rate_limit_exceeded when exhausted.
- Treat the process-local limiter as a demo implementation; use a shared counter for multi-instance deployment.
