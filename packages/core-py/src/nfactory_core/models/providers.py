"""AI provider connections and the model catalog.

No secret is ever stored here: `secret_ref` points into the secret store.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from nfactory_core.models.base import Base, created_column, id_column, optional_timestamp


class ProviderConnection(Base):
    __tablename__ = "provider_connections"
    id: Mapped[str] = id_column("pcn")
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(60))  # openai_api, codex_local, ...
    display_name: Mapped[str] = mapped_column(String(120))
    secret_ref: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(40), default="not_configured")
    config_non_secret: Mapped[dict[str, Any]] = mapped_column(default=dict)
    last_checked_at: Mapped[datetime | None] = optional_timestamp()
    # {"kind", "message"} of the last failed test; French, redacted, never a key.
    last_error: Mapped[dict[str, Any] | None] = mapped_column(default=None)

    __table_args__ = (UniqueConstraint("workspace_id", "kind", name="uq_provider_ws_kind"),)


class ModelCatalogEntry(Base):
    __tablename__ = "model_catalog"
    provider_kind: Mapped[str] = mapped_column(String(60), primary_key=True)
    model_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    capabilities: Mapped[dict[str, Any]] = mapped_column(default=dict)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | discovered
    reviewed_at: Mapped[datetime | None] = optional_timestamp()


class StoredSecret(Base):
    """A secret encrypted with Fernet (decision D10). Only `nfactory_core.secrets` reads it."""

    __tablename__ = "secrets"
    id: Mapped[str] = id_column("sec")
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = created_column()

    def __repr__(self) -> str:
        return f"StoredSecret(id={self.id!r})"
