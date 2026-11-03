"""Factory, provider and agent metrics of spec §14.1 (task 5.1).

Every figure is one query over `runs`, `events` and `approvals`, restricted to the runs a
`RunScope` selects (the caller's workspaces, then the overview filters). A figure with
nothing to measure is None, never 0.

Interface: RunScope, factory_metrics, provider_metrics, agent_metrics.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Float,
    Row,
    Select,
    and_,
    case,
    cast,
    distinct,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.dashboard import AgentMetric, FactoryMetrics, ProviderMetric
from app.services.identity import RequestContext
from nfactory_core.models import Approval, EventRecord, Project, Run
from nfactory_core.states import TERMINAL_STATES, RunState

TESTS = ("test.passed", "test.failed")
CALL = "agent.progress"
FAILURE = "provider.failed"


def number(key: str) -> ColumnElement[float]:
    """A payload value read as a number, or NULL when it is not one (an old event may hold
    "***REDACTED***" where a number belongs)."""
    value = EventRecord.payload_redacted[key]
    return case((func.jsonb_typeof(value) == "number", cast(value.astext, Float)), else_=None)


@dataclass(frozen=True)
class RunScope:
    """The runs every figure is computed on."""

    ctx: RequestContext
    days: int | None = None
    project_type: str | None = None

    def projects(self) -> Select[str]:
        query = select(Project.id).where(Project.workspace_id.in_(self.ctx.workspace_ids))
        if self.project_type is not None:
            query = query.where(Project.type == self.project_type)
        return query

    def runs(self) -> Select[str]:
        query = select(Run.id).where(Run.project_id.in_(self.projects()))
        if self.days is not None:
            query = query.where(Run.created_at >= datetime.now(UTC) - timedelta(days=self.days))
        return query


async def factory_metrics(session: AsyncSession, scope: RunScope) -> FactoryMetrics:
    runs = scope.runs()
    finished, completed, cost = (
        await session.execute(
            select(
                func.count().filter(Run.state.in_([s.value for s in TERMINAL_STATES])),
                func.count().filter(Run.state == RunState.COMPLETED),
                func.sum(Run.cost_estimate_usd),
            ).where(Run.id.in_(runs))
        )
    ).one()
    return FactoryMetrics(
        end_to_end_delivery_rate=completed / finished if finished else None,
        first_pass_test_rate=await _first_pass_rate(session, runs),
        repair_success_rate=await _repair_success_rate(session, runs),
        time_to_preview_seconds=None,  # no event records when a preview is first served
        time_to_draft_pr_seconds=None,  # draft PRs come from agent tasks, not from runs
        human_intervention_count=await session.scalar(
            select(func.count()).where(Approval.run_id.in_(runs), Approval.status != "pending")
        )
        or 0,
        cost_per_successful_delivery=float(cost) / completed if completed and cost else None,
        critical_policy_violation_count=await _delivered_with_findings(session, runs),
    )


async def _first_pass_rate(session: AsyncSession, runs: Select[str]) -> float | None:
    """Among runs whose tests ran, the share that never had a failing test."""
    failed_any = func.bool_or(EventRecord.type == "test.failed")
    per_run = (
        select(EventRecord.run_id, failed_any.label("failed"))
        .where(EventRecord.run_id.in_(runs), EventRecord.type.in_(TESTS))
        .group_by(EventRecord.run_id)
        .subquery()
    )
    tested, first_pass = (
        await session.execute(
            select(func.count(), func.count().filter(per_run.c.failed.is_(False)))
        )
    ).one()
    return first_pass / tested if tested else None


async def _repair_success_rate(session: AsyncSession, runs: Select[str]) -> float | None:
    """Among runs that went through the debug loop, the share delivered in the end."""
    repaired = select(EventRecord.run_id).where(
        EventRecord.run_id.in_(runs), EventRecord.type == "repair.started"
    )
    total, delivered = (
        await session.execute(
            select(func.count(), func.count().filter(Run.state == RunState.COMPLETED)).where(
                Run.id.in_(repaired)
            )
        )
    ).one()
    return delivered / total if total else None


async def _delivered_with_findings(session: AsyncSession, runs: Select[str]) -> int:
    """Delivered runs whose secret scan found something: the target is zero."""
    findings = number("findings")
    return (
        await session.scalar(
            select(func.count(distinct(EventRecord.run_id)))
            .join(Run, Run.id == EventRecord.run_id)
            .where(
                EventRecord.run_id.in_(runs),
                EventRecord.type == "security.scanned",
                Run.state == RunState.COMPLETED,
                findings > 0,
            )
        )
        or 0
    )


def _calls(runs: Select[str], *keys: str) -> Select[Any]:
    """Per group: model calls, latency percentiles, failures, tokens and cost."""
    payload = EventRecord.payload_redacted
    groups = [payload[key].astext.label(key) for key in keys]
    is_call = EventRecord.type == CALL
    duration = number("duration_s")
    cost = number("cost_usd")

    def tokens(key: str) -> ColumnElement[float]:
        return func.sum(case((is_call, number(key))))  # NULL when no call had a count

    return (
        select(
            *groups,
            func.count().filter(is_call).label("calls"),
            func.count().filter(EventRecord.type == FAILURE).label("failures"),
            func.percentile_cont(0.5).within_group(duration).filter(is_call).label("p50"),
            func.percentile_cont(0.95).within_group(duration).filter(is_call).label("p95"),
            tokens("input_tokens").label("input_tokens"),
            tokens("output_tokens").label("output_tokens"),
            func.sum(case((is_call, cost))).label("cost"),
            func.count().filter(and_(is_call, cost.is_(None))).label("unpriced"),
        )
        .where(EventRecord.run_id.in_(runs), EventRecord.type.in_([CALL, FAILURE]))
        .group_by(*groups)
        .order_by(*groups)
    )


async def provider_metrics(session: AsyncSession, scope: RunScope) -> list[ProviderMetric]:
    rows = await session.execute(_calls(scope.runs(), "provider", "model"))
    return [
        ProviderMetric(provider=row.provider or "—", model=row.model or "—", **_figures(row))
        for row in rows
    ]


async def agent_metrics(session: AsyncSession, scope: RunScope) -> list[AgentMetric]:
    # A call names its agent `agent`; a provider failure names it `role`.
    payload = EventRecord.payload_redacted
    agent = func.coalesce(payload["agent"].astext, payload["role"].astext).label("agent")
    base = _calls(scope.runs())
    rows = await session.execute(base.add_columns(agent).group_by(agent).order_by(agent))
    return [AgentMetric(agent=row.agent or "—", **_figures(row)) for row in rows]


def _figures(row: Row[Any]) -> dict[str, Any]:
    return {
        "calls": row.calls,
        "failures": row.failures,
        "latency_p50_s": row.p50,
        "latency_p95_s": row.p95,
        "input_tokens": None if row.input_tokens is None else int(row.input_tokens),
        "output_tokens": None if row.output_tokens is None else int(row.output_tokens),
        "cost_usd": float(row.cost) if row.cost is not None else None,
        "cost_complete": row.calls > 0 and row.unpriced == 0,
    }
