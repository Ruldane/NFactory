"""Users, workspaces (tenants) and memberships."""

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from nfactory_core.models.base import Base, created_column, id_column

ROLES = ("owner", "admin", "developer", "reviewer", "viewer")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = id_column("usr")
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    local_identity: Mapped[str | None] = mapped_column(String(200), unique=True)
    # SSO identity (ADR-0013): "<issuer>|<sub>", stable when the e-mail changes.
    oidc_subject: Mapped[str | None] = mapped_column(String(300), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = created_column()


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = id_column("wks")
    name: Mapped[str] = mapped_column(String(200))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    data_policy: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = created_column()


class Membership(Base):
    __tablename__ = "memberships"
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20))  # one of ROLES
