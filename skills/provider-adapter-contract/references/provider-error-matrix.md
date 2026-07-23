# Provider Error Matrix

| Source condition | Normalized error | Retryable |
|---|---|---|
| Timeout or deadline | provider_timeout | yes |
| HTTP 429 | provider_rate_limited | yes |
| Connection, 502, 503, 504 | provider_unavailable | yes |
| HTTP 401 or 403 | provider_authentication | no |
| HTTP 400, 404, 409, 422 | provider_request_invalid | no |
| Unknown SDK failure | provider_internal | no by default |

Do not include secrets, response bodies or vendor stack traces in normalized client messages.
