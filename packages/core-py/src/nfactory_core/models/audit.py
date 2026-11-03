"""Append-only audit trail of sensitive actions; details are redacted."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Identity, String
from sqlalchemy.orm import Mapped, mapped_column

from nfactory_core.models.base import Base, created_column


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str] = mapped_column(String(200))
    decision: Mapped[str | None] = mapped_column(String(20))
    redacted_details: Mapped[dict[str, Any]] = mapped_column(default=dict)
    timestamp: Mapped[datetime] = created_column()
