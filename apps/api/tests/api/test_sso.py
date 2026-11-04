"""Google sign-in (ADR-0013, spec F34). In SSO mode every API route needs a session,
admission is denied by default, a session lives only as a hash, and a state-changing
request must come from the dashboard's origin. Local mode is unchanged."""

import json
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient
from sqlalchemy import select, update

from nfactory_core.models import AuditLog, AuthSession, User

pytestmark = pytest.mark.integration

ISSUER = "https://accounts.google.com"
CLIENT_ID = "nfactory-test.apps.googleusercontent.com"
DASHBOARD = "http://127.0.0.1:3000"
DISCOVERY = {
    "issuer": ISSUER,
    "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_endpoint": "https://oauth2.googleapis.com/token",
    "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
}
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ADA = {"sub": "111", "email": "ada@example.fr", "name": "Ada Lovelace", "hd": "example.fr"}
BOB = {"sub": "222", "email": "bob@example.fr", "name": "Bob", "hd": "example.fr"}
GRACE = {"sub": "333", "email": "grace@gmail.com", "name": "Grace Hopper"}
MALLORY = {"sub": "444", "email": "mallory@evil.example", "name": "M", "hd": "evil.example"}


def google(claims: dict[str, object]) -> None:
    """Simulated Google: discovery, keys, and a token endpoint that signs `claims`
    with the nonce of the authorization request."""
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key()))
    respx.get(f"{ISSUER}/.well-known/openid-configuration").respond(json=DISCOVERY)
    respx.get(DISCOVERY["jwks_uri"]).respond(json={"keys": [{**public, "kid": "k1"}]})

    def token(request):  # type: ignore[no-untyped-def]
        now = int(time.time())
        body = {"iss": ISSUER, "aud": CLIENT_ID, "email_verified": True, "iat": now}
        body |= {"exp": now + 600, "nonce": google.nonce, **claims}  # type: ignore[attr-defined]
        signed = jwt.encode(body, KEY, algorithm="RS256", headers={"kid": "k1"})
        return respx.MockResponse(200, json={"id_token": signed, "access_token": "at"})

    respx.post(DISCOVERY["token_endpoint"]).mock(side_effect=token)


async def sign_in(client: AsyncClient, claims: dict[str, object]) -> str:
    """Runs the browser's side of the flow; returns where the callback sent it."""
    google(claims)
    start = await client.get("/api/v1/auth/login")
    assert start.status_code == 302
    query = parse_qs(urlsplit(start.headers["location"]).query)
    google.nonce = query["nonce"][0]  # type: ignore[attr-defined]
    done = await client.get(
        "/api/v1/auth/callback", params={"state": query["state"][0], "code": "c-1"}
    )
    assert done.status_code == 302
    return done.headers["location"]


async def test_local_mode_needs_no_sign_in(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/auth/config")).json() == {"mode": "local", "provider": None}
    assert (await client.get("/api/v1/projects")).status_code == 200
    disabled = await client.get("/api/v1/auth/login")
    assert disabled.status_code == 404
    assert disabled.json()["error"]["code"] == "sso_disabled"


async def test_sso_mode_closes_every_route_but_health_and_sign_in(sso_client: AsyncClient) -> None:
    config = (await sso_client.get("/api/v1/auth/config")).json()
    # What the sign-in screen tells the user (legal review §2, information).
    assert config == {
        "mode": "oidc",
        "provider": "Google",
        "session_hours": 12,
        "privacy_contact": "dpo@example.fr",
    }
    assert (await sso_client.get("/api/v1/health")).status_code == 200

    for path in ("/api/v1/projects", "/api/v1/me", "/api/v1/settings", "/api/v1/recipes"):
        closed = await sso_client.get(path)
        assert closed.status_code == 401, path
        assert closed.json()["error"]["code"] == "not_authenticated"


@respx.mock
async def test_an_owner_signs_in_and_gets_a_session_cookie(sso_client: AsyncClient) -> None:
    landed = await sign_in(sso_client, ADA)

    assert landed == "/"
    cookie = sso_client.cookies.get("nfactory_session")
    assert cookie
    me = (await sso_client.get("/api/v1/me")).json()
    assert me["display_name"] == "Ada Lovelace"
    assert me["workspaces"][0]["role"] == "owner"


@respx.mock
async def test_the_cookie_is_http_only_and_lax_and_the_base_keeps_only_a_hash(
    sso_client: AsyncClient,
) -> None:
    google(ADA)
    start = await sso_client.get("/api/v1/auth/login")
    query = parse_qs(urlsplit(start.headers["location"]).query)
    google.nonce = query["nonce"][0]  # type: ignore[attr-defined]
    done = await sso_client.get(
        "/api/v1/auth/callback", params={"state": query["state"][0], "code": "c"}
    )

    header = done.headers["set-cookie"]
    assert "HttpOnly" in header and "SameSite=lax" in header and "Path=/" in header
    token = sso_client.cookies.get("nfactory_session")
    sessions = sso_client._transport.app.state.database.sessions  # type: ignore[attr-defined]
    async with sessions() as session:
        stored = list(await session.scalars(select(AuthSession)))
    assert len(stored) == 1 and token not in stored[0].token_hash


@respx.mock
async def test_members_of_the_domain_join_as_viewers(sso_client: AsyncClient) -> None:
    await sign_in(sso_client, BOB)

    me = (await sso_client.get("/api/v1/me")).json()
    assert me["workspaces"][0]["role"] == "viewer"
    refused = await sso_client.post(
        "/api/v1/projects", json={"title": "x", "type": "excel"}, headers={"Origin": DASHBOARD}
    )
    assert refused.status_code == 403


@respx.mock
async def test_a_listed_personal_account_is_admitted(sso_client: AsyncClient) -> None:
    await sign_in(sso_client, GRACE)

    assert (await sso_client.get("/api/v1/me")).status_code == 200


@respx.mock
async def test_an_unlisted_domain_is_refused_and_audited(sso_client: AsyncClient) -> None:
    landed = await sign_in(sso_client, MALLORY)

    assert landed == "/?auth_error=not_allowed"
    assert "nfactory_session" not in sso_client.cookies
    sessions = sso_client._transport.app.state.database.sessions  # type: ignore[attr-defined]
    async with sessions() as session:
        denied = await session.scalar(select(AuditLog).where(AuditLog.action == "auth.denied"))
        users = list(await session.scalars(select(User).where(User.email == MALLORY["email"])))
    assert denied is not None and denied.decision == "denied"
    assert users == []  # a refused account leaves no member behind


@respx.mock
async def test_the_e_mail_domain_alone_does_not_admit(sso_client: AsyncClient) -> None:
    # A personal account whose address ends with the allowed domain, without "hd".
    landed = await sign_in(sso_client, {"sub": "555", "email": "eve@example.fr", "name": "Eve"})

    assert landed == "/?auth_error=not_allowed"


@respx.mock
async def test_a_state_is_used_once(sso_client: AsyncClient) -> None:
    google(ADA)
    start = await sso_client.get("/api/v1/auth/login")
    query = parse_qs(urlsplit(start.headers["location"]).query)
    google.nonce = query["nonce"][0]  # type: ignore[attr-defined]
    params = {"state": query["state"][0], "code": "c"}
    assert (await sso_client.get("/api/v1/auth/callback", params=params)).headers["location"] == "/"
    sso_client.cookies.clear()

    replay = await sso_client.get("/api/v1/auth/callback", params=params)

    assert replay.headers["location"] == "/?auth_error=state"
    unknown = await sso_client.get(
        "/api/v1/auth/callback", params={"state": "made-up", "code": "c"}
    )
    assert unknown.headers["location"] == "/?auth_error=state"


@respx.mock
async def test_the_provider_refusal_lands_on_an_error(sso_client: AsyncClient) -> None:
    landed = await sso_client.get("/api/v1/auth/callback", params={"error": "access_denied"})

    assert landed.headers["location"] == "/?auth_error=cancelled"


@respx.mock
async def test_signing_in_again_finds_the_same_member(sso_client: AsyncClient) -> None:
    await sign_in(sso_client, ADA)
    first = (await sso_client.get("/api/v1/me")).json()["user_id"]
    sso_client.cookies.clear()

    await sign_in(sso_client, {**ADA, "email": "ada.lovelace@example.fr"})

    assert (await sso_client.get("/api/v1/me")).json()["user_id"] == first


@respx.mock
async def test_sign_out_revokes_the_session(sso_client: AsyncClient) -> None:
    await sign_in(sso_client, ADA)
    token = sso_client.cookies.get("nfactory_session")

    out = await sso_client.post("/api/v1/auth/logout", headers={"Origin": DASHBOARD})

    assert out.status_code == 204
    sso_client.cookies.set("nfactory_session", token)  # a copied cookie is dead too
    assert (await sso_client.get("/api/v1/me")).status_code == 401


@respx.mock
async def test_an_expired_session_is_refused(sso_client: AsyncClient) -> None:
    await sign_in(sso_client, ADA)
    sessions = sso_client._transport.app.state.database.sessions  # type: ignore[attr-defined]
    async with sessions() as session:
        past = datetime.now(UTC) - timedelta(minutes=1)
        await session.execute(update(AuthSession).values(expires_at=past))
        await session.commit()

    assert (await sso_client.get("/api/v1/me")).status_code == 401


@respx.mock
async def test_a_change_from_another_origin_is_refused(sso_client: AsyncClient) -> None:
    await sign_in(sso_client, ADA)
    project = {"title": "Via SSO", "type": "excel"}

    forged = await sso_client.post(
        "/api/v1/projects", json=project, headers={"Origin": "https://evil.example"}
    )
    bare = await sso_client.post("/api/v1/projects", json=project)
    genuine = await sso_client.post("/api/v1/projects", json=project, headers={"Origin": DASHBOARD})

    assert forged.status_code == 403 and forged.json()["error"]["code"] == "csrf_rejected"
    assert bare.status_code == 403
    assert genuine.status_code == 201
