# NFactory worker (ARQ + LangGraph). Build context: repository root.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.22 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /srv
COPY pyproject.toml uv.lock ./
COPY packages/core-py/pyproject.toml packages/core-py/
COPY apps/api/pyproject.toml apps/api/
COPY apps/worker/pyproject.toml apps/worker/
RUN uv sync --frozen --no-dev --package nfactory-worker --no-install-workspace

COPY packages/core-py packages/core-py
COPY apps/worker apps/worker
RUN uv sync --frozen --no-dev --package nfactory-worker

RUN useradd --uid 10001 --no-create-home nfactory \
    && mkdir -p /data/artifacts /data/workspaces \
    && chown nfactory /data/artifacts /data/workspaces
USER nfactory
WORKDIR /srv/apps/worker
CMD ["arq", "nfactory_worker.main.WorkerSettings"]
