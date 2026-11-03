from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.context import Session
from app.services.readiness import check_all

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness only: says nothing about dependencies or configuration."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request, session: Session) -> JSONResponse:
    checks = await check_all(session, request.app.state.settings.redis_url)
    healthy = all(check["ok"] for check in checks.values())
    body: dict[str, Any] = {"status": "ok" if healthy else "degraded", "checks": checks}
    return JSONResponse(body, status_code=200 if healthy else 503)
