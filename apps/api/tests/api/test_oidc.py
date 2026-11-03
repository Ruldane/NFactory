"""OpenID Connect client (ADR-0013): the authorization URL, and an ID token accepted only
when Google's keys signed it for us, for this login attempt, and it has not expired."""

import base64
import hashlib
import json
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa

from app.services.oidc import OidcClient, OidcConfig, OidcError

ISSUER = "https://accounts.google.com"
CLIENT_ID = "nfactory-test.apps.googleusercontent.com"
REDIRECT = "http://127.0.0.1:3000/api/v1/auth/callback"
DISCOVERY = {
    "issuer": ISSUER,
    "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_endpoint": "https://oauth2.googleapis.com/token",
    "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
}

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks() -> dict[str, object]:
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key()))
    return {"keys": [{**public, "kid": "k1", "use": "sig", "alg": "RS256"}]}


def id_token(key: rsa.RSAPrivateKey = KEY, **claims: object) -> str:
    now = int(time.time())
    body = {
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "sub": "1234567890",
        "email": "ada@example.fr",
        "email_verified": True,
        "name": "Ada Lovelace",
        "hd": "example.fr",
        "nonce": "n-1",
        "iat": now,
        "exp": now + 600,
        **claims,
    }
    return jwt.encode(body, key, algorithm="RS256", headers={"kid": "k1"})


def provider(token: str) -> respx.Route:
    respx.get(f"{ISSUER}/.well-known/openid-configuration").respond(json=DISCOVERY)
    respx.get(DISCOVERY["jwks_uri"]).respond(json=_jwks())
    return respx.post(DISCOVERY["token_endpoint"]).respond(
        json={"access_token": "at", "id_token": token, "token_type": "Bearer"}
    )


def client() -> OidcClient:
    config = OidcConfig(
        issuer=ISSUER, client_id=CLIENT_ID, client_secret="s3cret", redirect_url=REDIRECT
    )
    return OidcClient(config, httpx.AsyncClient())


@respx.mock
async def test_the_authorization_url_asks_only_for_sign_in_with_pkce() -> None:
    provider(id_token())

    url = await client().authorization_url(state="st", nonce="n-1", verifier="v" * 50)

    query = parse_qs(urlsplit(url).query)
    assert url.startswith(DISCOVERY["authorization_endpoint"])
    assert query["scope"] == ["openid email profile"]
    assert query["response_type"] == ["code"]
    assert query["client_id"] == [CLIENT_ID] and query["redirect_uri"] == [REDIRECT]
    assert query["state"] == ["st"] and query["nonce"] == ["n-1"]
    expected = base64.urlsafe_b64encode(hashlib.sha256(b"v" * 50).digest()).rstrip(b"=")
    assert query["code_challenge"] == [expected.decode()]
    assert query["code_challenge_method"] == ["S256"]


@respx.mock
async def test_a_valid_code_returns_the_verified_identity() -> None:
    token_route = provider(id_token())

    identity = await client().exchange(code="c-1", verifier="v" * 50, nonce="n-1")

    assert identity.subject == f"{ISSUER}|1234567890"
    assert identity.email == "ada@example.fr" and identity.hosted_domain == "example.fr"
    assert identity.name == "Ada Lovelace"
    sent = parse_qs(token_route.calls.last.request.content.decode())
    assert sent["code"] == ["c-1"] and sent["code_verifier"] == ["v" * 50]
    assert sent["grant_type"] == ["authorization_code"]


@pytest.mark.parametrize(
    ("token", "reason"),
    [
        (id_token(aud="someone-else"), "audience"),
        (id_token(iss="https://evil.example"), "issuer"),
        (id_token(nonce="n-other"), "nonce"),
        (id_token(exp=int(time.time()) - 60), "expired"),
        (id_token(key=OTHER_KEY), "signature"),
        (id_token(email_verified=False), "email_unverified"),
    ],
)
@respx.mock
async def test_a_token_that_fails_a_check_is_refused(token: str, reason: str) -> None:
    provider(token)

    with pytest.raises(OidcError) as refused:
        await client().exchange(code="c-1", verifier="v" * 50, nonce="n-1")

    assert refused.value.reason == reason


@respx.mock
async def test_an_unsigned_token_is_refused() -> None:
    unsigned = jwt.encode({"iss": ISSUER, "aud": CLIENT_ID, "sub": "x"}, key=None, algorithm="none")
    provider(unsigned)

    with pytest.raises(OidcError) as refused:
        await client().exchange(code="c-1", verifier="v" * 50, nonce="n-1")

    assert refused.value.reason == "signature"


@respx.mock
async def test_a_rejected_code_is_an_error_without_the_provider_text() -> None:
    respx.get(f"{ISSUER}/.well-known/openid-configuration").respond(json=DISCOVERY)
    respx.post(DISCOVERY["token_endpoint"]).respond(
        400, json={"error": "invalid_grant", "error_description": "Bad Request s3cret"}
    )

    with pytest.raises(OidcError) as refused:
        await client().exchange(code="bad", verifier="v" * 50, nonce="n-1")

    assert refused.value.reason == "code_rejected"
    assert "s3cret" not in str(refused.value)
