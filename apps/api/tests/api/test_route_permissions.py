"""Every route that changes something states the permission it needs (ADR-0011)."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from fastapi.routing import APIRoute

from app.context import PERMISSION_DEPENDENCIES, require_session
from app.main import create_app
from nfactory_core.config import Settings

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
# Ending one's own session needs no permission, only the session itself (ADR-0013).
NO_PERMISSION = {"POST /api/v1/auth/logout"}
PUBLIC = ("/api/v1/health", "/api/v1/ready", "/api/v1/auth/")


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str  # with every router prefix
    calls: frozenset[object]  # its dependencies, including those of the routers above it


def _calls(dependant) -> set[object]:  # type: ignore[no-untyped-def]
    found = {dependant.call}
    for sub in dependant.dependencies:
        found |= _calls(sub)
    return found


def _endpoints(
    routes: Iterable[object], prefix: str = "", inherited: frozenset[object] = frozenset()
) -> Iterator[Endpoint]:
    """Every endpoint, through included routers. FastAPI 0.16x includes them lazily, so a
    route's own path and dependant miss its routers' prefixes and dependencies."""
    for route in routes:
        if isinstance(route, APIRoute):
            calls = frozenset(_calls(route.dependant)) | inherited
            for method in route.methods:
                yield Endpoint(method, prefix + route.path, calls)
        elif (included := getattr(route, "original_router", None)) is not None:
            context = getattr(route, "include_context", None)
            extra = list(included.dependencies) + list(getattr(context, "dependencies", []) or [])
            # A route's path already holds its own router's prefix; the include context
            # holds the prefixes of the routers above it.
            outer = getattr(context, "prefix", "") or prefix
            yield from _endpoints(included.routes, outer, inherited | {d.dependency for d in extra})


def _app_endpoints() -> list[Endpoint]:
    app = create_app(Settings(database_url="postgresql+psycopg://u:p@127.0.0.1:1/x"))
    return list(_endpoints(app.routes))


def test_every_mutating_route_requires_a_permission() -> None:
    guards = set(PERMISSION_DEPENDENCIES.values())

    endpoints = [e for e in _app_endpoints() if e.method in MUTATING]
    unguarded = [
        f"{e.method} {e.path}"
        for e in endpoints
        if not e.calls & guards and f"{e.method} {e.path}" not in NO_PERMISSION
    ]

    assert len(endpoints) > 20  # the walk really reached the endpoints
    assert "POST /api/v1/projects" in {f"{e.method} {e.path}" for e in endpoints}
    assert unguarded == []


def test_every_route_but_health_and_sign_in_needs_a_session() -> None:
    endpoints = [e for e in _app_endpoints() if e.path.startswith("/api/v1")]
    open_routes = [
        f"{e.method} {e.path}"
        for e in endpoints
        if not e.path.startswith(PUBLIC) and require_session not in e.calls
    ]

    assert len(endpoints) > 40
    assert "GET /api/v1/health" in {f"{e.method} {e.path}" for e in endpoints}
    assert open_routes == []
