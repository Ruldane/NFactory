"""Sandbox checks of a coding agent's change made on the user's machine (task 4.4).

The change lives in a worktree on the user's machine (bridge task); NFactory copies its
files into a throwaway workspace and runs the tests in its sandbox, never on the bridge.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from nfactory_core.models.base import Base, created_column, id_column, optional_timestamp

# queued -> running -> passed | failed | not_tested | error
CHECK_STATUSES = ("queued", "running", "passed", "failed", "not_tested", "error")


class AgentCheck(Base):
    __tablename__ = "agent_checks"
    id: Mapped[str] = id_column("agc")
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    task_id: Mapped[str] = mapped_column(String(20), index=True)
    repo_id: Mapped[str] = mapped_column(String(50))
    runtime: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    report: Mapped[dict[str, Any] | None] = mapped_column()
    error: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = created_column()
    finished_at: Mapped[datetime | None] = optional_timestamp()
