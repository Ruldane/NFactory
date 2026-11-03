"""SSRF guard for base URLs typed by a user (custom endpoint, Ollama).

The custom endpoint must be a public HTTPS address, unless its host is explicitly
allow-listed (`NFACTORY_ALLOWED_PRIVATE_LLM_HOSTS`). Ollama is local by nature, but
cloud metadata and unspecified addresses stay refused for everyone. The check runs at
configuration time and again before every request; redirects are never followed.
"""

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlsplit

Resolver = Callable[[str], list[str]]


class UnsafeUrlError(ValueError):
    pass


@dataclass(frozen=True)
class UrlPolicy:
    allow_http: bool = False
    allow_private: bool = False
    allowed_private_hosts: frozenset[str] = field(default_factory=frozenset)


def system_resolver(host: str) -> list[str]:
    return sorted({str(info[4][0]) for info in socket.getaddrinfo(host, None)})


def check_url(url: str, *, policy: UrlPolicy, resolver: Resolver = system_resolver) -> None:
    """Raise UnsafeUrlError unless `url` may be called under `policy`."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UnsafeUrlError("Adresse invalide : une URL http(s) complète est attendue.")
    if parts.username or parts.password:
        raise UnsafeUrlError("Adresse refusée : pas d'identifiants dans l'URL, utilisez la clé.")
    host = parts.hostname.lower()
    allow_listed = host in policy.allowed_private_hosts
    if parts.scheme == "http" and not (policy.allow_http or allow_listed):
        raise UnsafeUrlError("Adresse refusée : HTTPS est obligatoire pour un endpoint distant.")
    try:
        addresses = [ipaddress.ip_address(ip.split("%")[0]) for ip in resolver(host)]
    except (OSError, ValueError) as exc:
        raise UnsafeUrlError(f"Adresse introuvable : {host} ne se résout pas.") from exc
    if not addresses:
        raise UnsafeUrlError(f"Adresse introuvable : {host} ne se résout pas.")
    for address in addresses:
        if address.is_link_local or address.is_unspecified or address.is_multicast:
            # 169.254.169.254 is the cloud metadata endpoint: never reachable.
            raise UnsafeUrlError(f"Adresse refusée : {address} n'est jamais autorisée.")
        if not address.is_global and not (policy.allow_private or allow_listed):
            raise UnsafeUrlError(
                f"Adresse refusée : {host} pointe vers un réseau interne ({address}). "
                "Ajoutez l'hôte à NFACTORY_ALLOWED_PRIVATE_LLM_HOSTS si c'est voulu."
            )
