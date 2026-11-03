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


class Filters(BaseModel):
    days: int | None
    project_type: str | None


class FactoryMetrics(BaseModel):
    """NFactory metrics of spec §14.1. None: nothing to measure (yet), never a fake 0."""

    end_to_end_delivery_rate: float | None
    first_pass_test_rate: float | None
    repair_success_rate: float | None
    time_to_preview_seconds: float | None
    time_to_draft_pr_seconds: float | None
    human_intervention_count: int
    cost_per_successful_delivery: float | None
    critical_policy_violation_count: int


class CallMetrics(BaseModel):
    calls: int
    failures: int
    latency_p50_s: float | None
    latency_p95_s: float | None
    input_tokens: int | None  # None: no call reported a count
    output_tokens: int | None
    cost_usd: float | None
    cost_complete: bool  # every call had a known price


class ProviderMetric(CallMetrics):
    provider: str
    model: str


class AgentMetric(CallMetrics):
    agent: str


class DashboardSummary(BaseModel):
    filters: Filters
    demo_data: bool
    projects: int
    runs: RunCounts
    # None means "not measurable yet" (no finished run), never a fake 0.
    success_rate: float | None
    avg_duration_seconds: float | None
    cost_estimate_usd: float | None
    approvals_pending: int
    recent_runs: list[RecentRun]
    metrics: FactoryMetrics
    providers: list[ProviderMetric]
    agents: list[AgentMetric]
