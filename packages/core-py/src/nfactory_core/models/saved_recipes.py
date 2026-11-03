"""Reusable factory recipes (spec F38): a workflow saved by a workspace to run again."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from nfactory_core.models.base import Base, created_column, id_column


class SavedRecipe(Base):
    __tablename__ = "saved_recipes"
    id: Mapped[str] = id_column("rcp")
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(5000), default="")
    project_type: Mapped[str] = mapped_column(String(30))
    # The factory recipe kind the project used (`projects.template_id`), if not the default.
    template_id: Mapped[str | None] = mapped_column(String(100))
    request: Mapped[str] = mapped_column(Text)
    # The delivered run it was saved from; kept as text so deleting the run keeps the recipe.
    source_run_id: Mapped[str | None] = mapped_column(String(32))
    created_by: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = created_column()
    uses: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
