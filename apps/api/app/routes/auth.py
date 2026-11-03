"""Sign-in routes (ADR-0013). Public: they are how a session is opened."""

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from app.context import Session, check_origin
from app.errors import AppError
from app.services import auth
from app.services.oidc import OidcClient
from nfactory_core.config import Settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _oidc(request: Request) -> OidcClient:
    settings = _settings(request)
    if settings.nfactory_auth_mode == "local":
        raise AppError(404, "sso_disabled", "La connexion SSO n'est pas activée (mode local).")
    oidc: OidcClient | None = request.app.state.oidc
    if oidc is None:
        raise AppError(
            503,
            "sso_not_configured",
            "Le SSO est activé mais le client OAuth n'est pas renseigné (identifiant et secret).",
        )
    return oidc


def _provider_label(settings: Settings) -> str:
    return "Google" if "accounts.google.com" in settings.nfactory_oidc_issuer else "OpenID Connect"


@router.get("/config")
async def config(request: Request) -> dict[str, str | None]:
    """How the dashboard should sign in: no sign-in at all in local mode."""
    settings = _settings(request)
    if settings.nfactory_auth_mode == "local":
        return {"mode": "local", "provider": None}
    return {"mode": "oidc", "provider": _provider_label(settings)}


@router.get("/login")
async def login(request: Request, session: Session) -> RedirectResponse:
    url = await auth.start_login(session, _oidc(request))
    return RedirectResponse(url, status_code=302)


@router.get("/callback")
async def callback(
    request: Request,
    session: Session,
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    oidc = _oidc(request)
    if error:
        return RedirectResponse("/?auth_error=cancelled", status_code=302)
    if not state or not code:
        return RedirectResponse("/?auth_error=state", status_code=302)
    settings = _settings(request)
    policy = auth.Policy.from_settings(settings)
    try:
        token = await auth.finish_login(session, oidc, policy, state=state, code=code)
    except auth.LoginRefused as refused:
        return RedirectResponse(f"/?auth_error={refused.code}", status_code=302)
    landed = RedirectResponse("/", status_code=302)
    landed.set_cookie(
        auth.COOKIE,
        token,
        max_age=int(policy.ttl.total_seconds()),
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.nfactory_oidc_redirect_url.startswith("https://"),
    )
    return landed


@router.post("/logout", status_code=204)
async def logout(request: Request, session: Session) -> Response:
    check_origin(request)
    await auth.logout(session, request.cookies.get(auth.COOKIE))
    done = Response(status_code=204)
    done.delete_cookie(auth.COOKIE, path="/")
    return done
