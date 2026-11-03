# NFactory API. Build context: repository root.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.22 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /srv
# Dependencies first (cached layer), then sources.
COPY pyproject.toml uv.lock ./
COPY packages/core-py/pyproject.toml packages/core-py/
COPY apps/api/pyproject.toml apps/api/
COPY apps/worker/pyproject.toml apps/worker/
RUN uv sync --frozen --no-dev --package nfactory-api --no-install-workspace

COPY packages/core-py packages/core-py
COPY apps/api apps/api
RUN uv sync --frozen --no-dev --package nfactory-api

# Unprivileged runtime user; the artifacts volume inherits this ownership.
RUN useradd --uid 10001 --no-create-home nfactory \
    && mkdir -p /data/artifacts && chown nfactory /data/artifacts
USER nfactory
WORKDIR /srv/apps/api
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
