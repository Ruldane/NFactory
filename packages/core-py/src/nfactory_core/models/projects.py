"""Projects: the unit a user creates and iterates on."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nfactory_core.models.base import Base, created_column, id_column, utcnow

if TYPE_CHECKING:
    from nfactory_core.models.runs import Run

# Valid `type` values: nfactory_core.catalog.PROJECT_TYPES


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = id_column("proj")
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String(30))  # a catalog project_type
    template_id: Mapped[str | None] = mapped_column(String(100))
    repo_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default="active")
    # Synthetic data, shown as "Demo data" in the UI.
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    runs: Mapped[list["Run"]] = relationship(back_populates="project")
