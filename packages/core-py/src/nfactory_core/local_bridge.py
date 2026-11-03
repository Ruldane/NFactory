"""The paired local bridge, as both the API and the worker see it (ADR-0008).

Pairing stores the bridge token encrypted in a `local_bridge` connection of the workspace.
It is read at the last moment and never returned.

Interface: KIND, bridge_token.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from nfactory_core.connections import workspace_connections
from nfactory_core.secrets import SecretStore, SecretUnreadableError

KIND = "local_bridge"


async def bridge_token(session: AsyncSession, workspace_id: str, store: SecretStore) -> str | None:
    """The bridge token, or None when the workspace is not paired (or its key changed)."""
    row = (await workspace_connections(session, workspace_id)).get(KIND)
    if row is None or row.secret_ref is None:
        return None
    try:
        return await store.get(session, row.secret_ref)
    except SecretUnreadableError:
        return None  # the secret key changed: pairing again is the only way
