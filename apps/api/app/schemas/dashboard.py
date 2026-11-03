"""Overview KPIs. Every number comes from a database query, never a constant."""

from datetime import datetime

from pydantic import BaseModel


class RunCounts(BaseModel):
    total: int
    active: int
    completed: int
    partial: int
    failed: int
    cancelled: int


class StepBrief(BaseModel):
    name: str
    agent_role: str
    state: str
    attempts: int


class RecentRun(BaseModel):
    id: str
    project_id: str
    project_title: str
    state: str
    is_demo: bool
    created_at: datetime
    finished_at: datetime | None
    steps: list[StepBrief]  # ordered by position


class DashboardSummary(BaseModel):
    demo_data: bool
    projects: int
    runs: RunCounts
    # None means "not measurable yet" (no finished run), never a fake 0.
    success_rate: float | None
    avg_duration_seconds: float | None
    cost_estimate_usd: float | None
    approvals_pending: int
    recent_runs: list[RecentRun]
