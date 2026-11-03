"""Versioned golden-path template manifests."""

from typing import Any

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from nfactory_core.models.base import Base, id_column


class TemplateVersion(Base):
    __tablename__ = "template_versions"
    id: Mapped[str] = id_column("tpl")
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(30))
    manifest: Mapped[dict[str, Any]] = mapped_column(default=dict)
    checksum: Mapped[str] = mapped_column(String(80))
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("name", "version", name="uq_template_name_version"),)
