"""Secret store (decision D10): provider keys encrypted at rest.

A connection only keeps a reference:
- `db:<id>` points to a Fernet-encrypted row in `secrets`;
- `env:<NAME>` points to an environment variable (a key set in `.env`).

The Fernet key is derived from NFACTORY_SECRET_KEY (generated at bootstrap) with HKDF,
so rotating that variable makes stored keys unreadable: they must be entered again.
Interface: `SecretStore`, `SecretKeyMissingError`, `SecretUnreadableError`.
"""

import base64
import os
import re
from collections.abc import Mapping

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy.ext.asyncio import AsyncSession

from nfactory_core.models import StoredSecret

_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")


class SecretKeyMissingError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "NFACTORY_SECRET_KEY est vide : relancez scripts/dev pour le générer, "
            "puis enregistrez la clé à nouveau."
        )


class SecretUnreadableError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "Clé enregistrée illisible (NFACTORY_SECRET_KEY a changé) : saisissez-la à nouveau."
        )


def _fernet(master_key: str) -> Fernet:
    if not master_key:
        raise SecretKeyMissingError
    derived = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=b"nfactory", info=b"nfactory-secrets-v1"
    ).derive(master_key.encode())
    return Fernet(base64.urlsafe_b64encode(derived))


class SecretStore:
    def __init__(self, master_key: str, env: Mapping[str, str] | None = None) -> None:
        self._master_key = master_key
        self._env = os.environ if env is None else env

    async def put(self, session: AsyncSession, workspace_id: str, value: str) -> str:
        token = _fernet(self._master_key).encrypt(value.encode())
        row = StoredSecret(workspace_id=workspace_id, ciphertext=token)
        session.add(row)
        await session.flush()
        return f"db:{row.id}"

    async def get(self, session: AsyncSession, ref: str | None) -> str | None:
        kind, _, key = (ref or "").partition(":")
        if kind == "env":
            value = self._env.get(key) if _ENV_NAME.match(key) else None
            return value or None
        if kind != "db":
            return None
        row = await session.get(StoredSecret, key)
        if row is None:
            return None
        try:
            return _fernet(self._master_key).decrypt(row.ciphertext).decode()
        except InvalidToken as exc:
            raise SecretUnreadableError from exc

    async def delete(self, session: AsyncSession, ref: str | None) -> None:
        kind, _, key = (ref or "").partition(":")
        if kind == "db":
            row = await session.get(StoredSecret, key)
            if row is not None:
                await session.delete(row)
                await session.flush()
