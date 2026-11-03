"""Pairing between NFactory and the bridge on the user's machine.

The bridge prints a one-time code in the user's terminal; NFactory sends it back once and
receives a long-lived token. Only the token's SHA-256 is kept on disk, so reading the store
file never gives a usable token. A code expires, is single use, and is burnt after
`max_attempts` wrong guesses: the user then asks the bridge for a new one.
"""

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections.abc import Callable
from pathlib import Path

# No 0/O, 1/I/L: the code is read on a screen and typed by hand.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_TTL_S = 600
MAX_ATTEMPTS = 5


class PairingRefused(ValueError):
    """The code is wrong, expired, burnt or already used."""


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Pairing:
    def __init__(
        self,
        store: Path,
        *,
        clock: Callable[[], float] = time.monotonic,
        code_ttl_s: float = CODE_TTL_S,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        self._store = store
        self._clock = clock
        self._ttl = code_ttl_s
        self._max_attempts = max_attempts
        self._lock = threading.Lock()
        self._code: str | None = None
        self._code_expires = 0.0
        self._attempts = 0
        self._token_sha256 = self._load()

    @property
    def paired(self) -> bool:
        return self._token_sha256 is not None

    def new_code(self) -> str:
        """A fresh code like `ABCD-EFGH`; it replaces any previous one."""
        raw = "".join(secrets.choice(_ALPHABET) for _ in range(8))
        with self._lock:
            self._code = raw
            self._code_expires = self._clock() + self._ttl
            self._attempts = 0
        return f"{raw[:4]}-{raw[4:]}"

    def pair(self, code: str) -> str:
        """Trade a valid code for a new token (the previous token stops working)."""
        typed = code.strip().upper().replace("-", "").replace(" ", "")
        with self._lock:
            if self._code is None or self._clock() > self._code_expires:
                self._code = None
                raise PairingRefused("Code d'appairage expiré : demandez-en un nouveau au pont.")
            if not hmac.compare_digest(typed.encode(), self._code.encode()):
                self._attempts += 1
                if self._attempts >= self._max_attempts:
                    self._code = None
                raise PairingRefused("Code d'appairage incorrect.")
            self._code = None
            token = secrets.token_urlsafe(32)
            self._token_sha256 = _digest(token)
            self._save()
        return token

    def authorized(self, token: str) -> bool:
        expected = self._token_sha256
        if expected is None or not token:
            return False
        return hmac.compare_digest(_digest(token), expected)

    def unpair(self) -> None:
        with self._lock:
            self._token_sha256 = None
            self._store.unlink(missing_ok=True)

    def _load(self) -> str | None:
        try:
            data = json.loads(self._store.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        value = data.get("token_sha256") if isinstance(data, dict) else None
        return value if isinstance(value, str) and len(value) == 64 else None

    def _save(self) -> None:
        self._store.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._store.with_suffix(".tmp")
        temporary.write_text(json.dumps({"token_sha256": self._token_sha256}), encoding="utf-8")
        os.replace(temporary, self._store)
