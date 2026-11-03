"""Runs, their steps, their event log and the approvals they wait on."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nfactory_core.models.base import Base, created_column, id_column, optional_timestamp
from nfactory_core.models.projects import Project
from nfactory_core.states import RunState, StepState


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = id_column("run")
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    # Incremental change requests create a child run (spec §3.5).
    parent_run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"))
    request: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(30), default=RunState.DRAFT.value, index=True)
    budget: Mapped[dict[str, Any]] = mapped_column(default=dict)
    provider_config: Mapped[dict[str, Any]] = mapped_column(default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    trace_id: Mapped[str | None] = mapped_column(String(64))
    cost_estimate_usd: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created_column()
    started_at: Mapped[datetime | None] = optional_timestamp()
    finished_at: Mapped[datetime | None] = optional_timestamp()

    project: Mapped[Project] = relationship(back_populates="runs")
    steps: Mapped[list["RunStep"]] = relationship(back_populates="run", order_by="RunStep.position")


class RunStep(Base):
    __tablename__ = "run_steps"
    id: Mapped[str] = id_column("step")
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(60))
    agent_role: Mapped[str] = mapped_column(String(40))
    state: Mapped[str] = mapped_column(String(20), default=StepState.PENDING.value)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    output: Mapped[dict[str, Any]] = mapped_column(default=dict)
    started_at: Mapped[datetime | None] = optional_timestamp()
    ended_at: Mapped[datetime | None] = optional_timestamp()
    error: Mapped[str | None] = mapped_column(Text)

    run: Mapped[Run] = relationship(back_populates="steps")


class EventRecord(Base):
    """Persisted copy of `nfactory_core.events.Event`, payload already redacted."""

    __tablename__ = "events"
    # Monotonic `seq` doubles as the SSE Last-Event-ID for resumable streams.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id: Mapped[str] = mapped_column(String(32), unique=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    step_id: Mapped[str | None] = mapped_column(String(32))
    type: Mapped[str] = mapped_column(String(40))
    schema_version: Mapped[str] = mapped_column(String(8), default="1")
    payload_redacted: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = created_column()

    __table_args__ = (Index("ix_events_run_seq", "run_id", "seq"),)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = id_column("apr")
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(60))  # plan | github_push | privileged_exec
    summary: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected
    requester_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approver_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = created_column()
    decided_at: Mapped[datetime | None] = optional_timestamp()
