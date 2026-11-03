"""Files produced by runs (ZIP, xlsx, scripts, reports)."""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from nfactory_core.models.base import Base, created_column, id_column


class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = id_column("art")
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"))
    filename: Mapped[str] = mapped_column(String(300))
    mime: Mapped[str] = mapped_column(String(120))
    storage_key: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(80))  # "sha256:<hex>"
    size: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = created_column()
