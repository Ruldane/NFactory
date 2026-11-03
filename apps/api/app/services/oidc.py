"""OpenID Connect client for sign-in (ADR-0013): Authorization Code with PKCE.

Generic OIDC; Google is only the default issuer. The ID token is trusted only when the
issuer's published keys signed it (RS256), for our client, for this login's nonce, and it
has not expired. Provider error text never leaves this module: it may echo request data.
"""

import base64
import hashlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

SCOPES = "openid email profile"
_ALGORITHMS = ["RS256"]
_LEEWAY_S = 60


class OidcError(Exception):
    """A sign-in that must not go through. `reason` is a stable slug, safe to show."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class OidcConfig:
    issuer: str
    client_id: str
    client_secret: str
    redirect_url: str


@dataclass(frozen=True)
class Identity:
    subject: str  # "<issuer>|<sub>": stable across e-mail changes
    email: str
    name: str
    hosted_domain: str | None  # Google Workspace domain ("hd"), None for a personal account


def code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class OidcClient:
    def __init__(self, config: OidcConfig, http: httpx.AsyncClient) -> None:
        self._config = config
        self._http = http
        self._discovery: dict[str, Any] | None = None

    async def close(self) -> None:
        await self._http.aclose()

    async def authorization_url(self, *, state: str, nonce: str, verifier: str) -> str:
        endpoint = (await self._metadata())["authorization_endpoint"]
        query = {
            "response_type": "code",
            "client_id": self._config.client_id,
            "redirect_uri": self._config.redirect_url,
            "scope": SCOPES,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge(verifier),
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        return f"{endpoint}?{urlencode(query)}"

    async def exchange(self, *, code: str, verifier: str, nonce: str) -> Identity:
        metadata = await self._metadata()
        try:
            response = await self._http.post(
                metadata["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "code_verifier": verifier,
                    "redirect_uri": self._config.redirect_url,
                    "client_id": self._config.client_id,
                    "client_secret": self._config.client_secret,
                },
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise OidcError("provider_unreachable") from exc
        if response.status_code != 200:
            raise OidcError("code_rejected")
        token = response.json().get("id_token")
        if not isinstance(token, str):
            raise OidcError("no_id_token")
        claims = await self._verify(token, metadata["jwks_uri"])
        if claims.get("nonce") != nonce:
            raise OidcError("nonce")
        if claims.get("email_verified") is not True or not claims.get("email"):
            raise OidcError("email_unverified")
        email = str(claims["email"]).lower()
        hosted = claims.get("hd")
        return Identity(
            subject=f"{claims['iss']}|{claims['sub']}",
            email=email,
            name=str(claims.get("name") or email),
            hosted_domain=str(hosted).lower() if hosted else None,
        )

    async def _verify(self, token: str, jwks_uri: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise OidcError("signature") from exc
        if header.get("alg") not in _ALGORITHMS:
            raise OidcError("signature")
        key = await self._key(jwks_uri, header.get("kid"))
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=_ALGORITHMS,
                audience=self._config.client_id,
                issuer=self._config.issuer,
                leeway=_LEEWAY_S,
                options={"require": ["iss", "aud", "sub", "exp", "iat"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise OidcError("expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise OidcError("audience") from exc
        except jwt.InvalidIssuerError as exc:
            raise OidcError("issuer") from exc
        except jwt.PyJWTError as exc:
            raise OidcError("signature") from exc
        return claims

    async def _key(self, jwks_uri: str, kid: object) -> Any:
        try:
            response = await self._http.get(jwks_uri)
            response.raise_for_status()
            keys = jwt.PyJWKSet.from_dict(response.json())
        except (httpx.HTTPError, jwt.PyJWTError, ValueError) as exc:
            raise OidcError("provider_unreachable") from exc
        for candidate in keys.keys:
            if candidate.key_id == kid:
                return candidate.key
        raise OidcError("signature")

    async def _metadata(self) -> dict[str, Any]:
        if self._discovery is None:
            url = f"{self._config.issuer.rstrip('/')}/.well-known/openid-configuration"
            try:
                response = await self._http.get(url)
                response.raise_for_status()
                metadata = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise OidcError("provider_unreachable") from exc
            if metadata.get("issuer") != self._config.issuer:
                raise OidcError("issuer")
            self._discovery = metadata
        return self._discovery
