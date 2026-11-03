"""Link between a project and its GitHub branch / pull request (spec §13)."""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from nfactory_core.models.base import Base, optional_timestamp


class GithubLink(Base):
    __tablename__ = "github_links"
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    owner: Mapped[str] = mapped_column(String(100))
    repo: Mapped[str] = mapped_column(String(100))
    branch: Mapped[str | None] = mapped_column(String(200))
    pr_number: Mapped[int | None] = mapped_column(Integer)
    last_synced: Mapped[datetime | None] = optional_timestamp()
