"""Normalized provider errors (spec §6.6): one `ProviderError` whatever the provider.

`classify_http_error` turns a failed response into a kind. The HTTP status alone is not
enough: each provider signals quota and rate limits its own way (see the per-provider
rules below, from docs/research/providers.md).
"""

from collections.abc import Callable, Mapping
from typing import Any, Literal

from nfactory_core.events.redaction import redact
from nfactory_core.providers.specs import label

ErrorKind = Literal[
    "auth",
    "quota",
    "rate_limit",
    "timeout",
    "unavailable",
    "bad_request",
    "not_found",
    "unsupported",
    "invalid_response",
    "blocked",
]

RETRYABLE: frozenset[str] = frozenset({"rate_limit", "timeout", "unavailable"})

_MESSAGES: dict[str, str] = {
    "auth": "clé refusée ou accès non autorisé : vérifiez la clé et le compte",
    "quota": "quota ou crédit épuisé : rechargez le compte ou relevez la limite de dépenses",
    "rate_limit": "limite de débit atteinte : nouvel essai après une pause",
    "timeout": "pas de réponse dans le délai imparti",
    "unavailable": "service indisponible ou surchargé",
    "bad_request": "requête refusée par le fournisseur",
    "not_found": "modèle ou ressource introuvable chez ce fournisseur",
    "unsupported": "fonction non prise en charge par ce fournisseur ou ce modèle",
    "invalid_response": "réponse illisible du fournisseur",
    "blocked": "adresse refusée par la protection réseau (SSRF)",
}

_DETAIL_MAX = 300


class ProviderError(Exception):
    def __init__(
        self,
        kind: ErrorKind,
        *,
        provider: str,
        status: int | None = None,
        detail: str = "",
        retry_after: float | None = None,
    ) -> None:
        self.kind = kind
        self.provider = provider
        self.status = status
        # Provider text may echo part of a key: redact, then cut.
        self.detail = str(redact(detail))[:_DETAIL_MAX]
        self.retry_after = retry_after
        super().__init__(self.message)

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE

    @property
    def message(self) -> str:
        """French, safe to show to the user and to store in events."""
        return f"{label(self.provider)} : {_MESSAGES[self.kind]}."

    def as_payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "kind": self.kind,
            "status": self.status,
            "message": self.message,
            "detail": self.detail,
        }


# --- per-provider rules: (status, body) -> kind, or None to use the status ----------

Rule = Callable[[int, Mapping[str, Any]], ErrorKind | None]


def _error(body: Mapping[str, Any]) -> Mapping[str, Any]:
    value = body.get("error")
    return value if isinstance(value, Mapping) else {}


def _openai(status: int, body: Mapping[str, Any]) -> ErrorKind | None:
    err = _error(body)
    quota_codes = {
        "credit_balance_exhausted",
        "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
        "insufficient_quota",
    }
    if status == 429 and (
        err.get("code") in quota_codes or err.get("type") == "insufficient_quota"
    ):
        return "quota"
    return None


def _anthropic(status: int, body: Mapping[str, Any]) -> ErrorKind | None:
    err = _error(body)
    details = err.get("details")
    code = details.get("error_code") if isinstance(details, Mapping) else None
    if status == 429 and code == "enforced_spend_limit_reached":
        return "quota"
    message = str(err.get("message", ""))
    if status == 400 and message.startswith("You have reached your specified API usage limits"):
        return "quota"
    return None


def _zai(status: int, body: Mapping[str, Any]) -> ErrorKind | None:
    try:
        code = int(str(_error(body).get("code", "")))
    except ValueError:
        return None
    if code in {1302, 1305}:
        return "rate_limit"
    if code == 1113 or 1308 <= code <= 1321:
        return "quota"
    if 1000 <= code <= 1005:
        return "auth"
    return None


def _kimi(status: int, body: Mapping[str, Any]) -> ErrorKind | None:
    return {
        "rate_limit_reached_error": "rate_limit",
        "exceeded_current_quota_error": "quota",
        "engine_overloaded_error": "unavailable",
    }.get(str(_error(body).get("type", "")))  # type: ignore[return-value]


def _qwen(status: int, body: Mapping[str, Any]) -> ErrorKind | None:
    # Code and message both matter: Throttling.AllocationQuota is a rate limit, except
    # when its message says the free allocation is used up.
    err = _error(body)
    code = str(body.get("code") or err.get("code") or "")
    message = str(body.get("message") or err.get("message") or "").lower()
    if "free allocated quota exceeded" in message or code == "AllocationQuota.FreeTierOnly":
        return "quota"
    if code == "Arrearage" or code.endswith("BillOverdue") or "out_of_service" in code.lower():
        return "quota"
    if code.startswith("Throttling") or code in {"insufficient_quota", "limit_requests"}:
        return "rate_limit"
    return None


_MINIMAX_CODES: dict[int, ErrorKind] = {
    **dict.fromkeys((1002, 1039, 1041, 1045, 2045, 2046, 2047, 2062, 2064), "rate_limit"),
    **dict.fromkeys((1008, 2053, 2056, 2067), "quota"),
    **dict.fromkeys((1004, 2049), "auth"),
    **dict.fromkeys((2022, 2061, 2068, 2069), "not_found"),
}


def minimax_status(body: Mapping[str, Any]) -> int:
    """MiniMax may answer HTTP 200 with an error in `base_resp`; 0 means success."""
    base = body.get("base_resp")
    if not isinstance(base, Mapping):
        return 0
    try:
        return int(base.get("status_code") or 0)
    except (TypeError, ValueError):
        return 0


def _minimax(status: int, body: Mapping[str, Any]) -> ErrorKind | None:
    code = minimax_status(body)
    if code:
        return _MINIMAX_CODES.get(code, "bad_request")
    return None


_RULES: dict[str, Rule] = {
    "openai_api": _openai,
    "anthropic_api": _anthropic,
    "zai_glm_api": _zai,
    "moonshot_kimi_api": _kimi,
    "qwen_api": _qwen,
    "minimax_api": _minimax,
}


def _by_status(status: int) -> ErrorKind:
    if status in (401, 403):
        return "auth"
    if status == 402:
        return "quota"
    if status == 404:
        return "not_found"
    if status in (408, 504):
        return "timeout"
    if status == 429:
        return "rate_limit"
    if status >= 500:
        return "unavailable"
    return "bad_request"


def _detail(body: Mapping[str, Any]) -> str:
    err = body.get("error")
    if isinstance(err, str):
        return err
    if isinstance(err, Mapping):
        return str(err.get("message") or err.get("type") or "")
    base = body.get("base_resp")
    if isinstance(base, Mapping):
        return str(base.get("status_msg") or "")
    return str(body.get("message") or "")


def _retry_after(headers: Mapping[str, str]) -> float | None:
    value = {k.lower(): v for k, v in headers.items()}.get("retry-after")
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def classify_http_error(
    provider: str, status: int, body: Mapping[str, Any], headers: Mapping[str, str]
) -> ProviderError:
    rule = _RULES.get(provider)
    kind = (rule(status, body) if rule else None) or _by_status(status)
    return ProviderError(
        kind,
        provider=provider,
        status=status,
        detail=_detail(body),
        retry_after=_retry_after(headers),
    )


def check_vectors(provider: str, vectors: list[list[float]], expected: int) -> list[list[float]]:
    """One non-empty vector per input text, or the reply is unusable."""
    if len(vectors) != expected or any(not v for v in vectors):
        raise ProviderError(
            "invalid_response",
            provider=provider,
            detail=f"{len(vectors)} vecteurs reçus pour {expected} textes",
        )
    return vectors
