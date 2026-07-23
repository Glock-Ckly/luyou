# Deployment

## Local

1. Install Python 3.12 dependencies with pip install -e .
2. Configure relay credentials without committing them.
3. Set MODEL_ROUTER_API_TOKEN for any shared environment.
4. Run python scripts/dashboard_server.py.
5. Verify GET /health and open http://127.0.0.1:1785.

## Docker Compose

1. Copy values from config/runtime.env.example into a private environment file.
2. Pass those values to Compose and run docker compose up --build.
3. Verify the container health check before sending traffic.

## Security boundary

- Terminate TLS at a trusted reverse proxy.
- Require Bearer authentication outside a single-user loopback demo.
- Keep CORS origins explicit.
- Restrict execution to configured work directory roots.
- Never bake provider credentials into the image or repository.

## Deferred runtime

proto/model_router.proto documents a future service boundary. The current release is a modular monolith and does not claim a running gRPC server.
