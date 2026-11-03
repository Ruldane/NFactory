"""Evaluation suites, cases and results (spec §14.2)."""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from nfactory_core.models.base import Base, created_column, id_column


class EvaluationSuite(Base):
    __tablename__ = "evaluation_suites"
    id: Mapped[str] = id_column("evs")
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")


class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"
    id: Mapped[str] = id_column("evc")
    suite_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_suites.id", ondelete="CASCADE"), index=True
    )
    input: Mapped[dict[str, Any]] = mapped_column(default=dict)
    expected_behavior: Mapped[dict[str, Any]] = mapped_column(default=dict)
    tags: Mapped[list[Any]] = mapped_column(default=list)


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"
    id: Mapped[str] = id_column("evr")
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    case_id: Mapped[str] = mapped_column(ForeignKey("evaluation_cases.id", ondelete="CASCADE"))
    passed: Mapped[bool] = mapped_column("pass", Boolean)
    metrics: Mapped[dict[str, Any]] = mapped_column(default=dict)
    reviewer: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = created_column()
