FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_ROUTER_HOST=0.0.0.0 \
    MODEL_ROUTER_PORT=1785 \
    MODEL_ROUTER_ALLOWED_WORKDIRS=/app

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir "litellm>=1.70,<2" "PyYAML>=6,<7"
COPY . .

EXPOSE 1785
HEALTHCHECK --interval=15s --timeout=3s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:1785/health', timeout=2)"]
CMD ["python", "scripts/dashboard_server.py"]
