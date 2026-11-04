"""Retention (ADR-0015): delete what each workspace chose not to keep, then sweep what
no row points to any more.

Rows go first, files after: the database is the only source of truth. The sweep removes
the `run_*` folders (deliverables, workspaces) and the LangGraph checkpoints whose run
is gone, whoever deleted it: this purge, or the API deleting a project (it cannot write
to the workspaces volume). An interrupted sweep simply finishes at the next one.

Interface: purge_expired, sweep_orphans, apply_retention, PurgeReport, SweepReport.
"""

import logging
import re
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from sqlalchemy import CursorResult, Executable, delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nfactory_core.config import Settings
from nfactory_core.models import Artifact, AuditLog, Project, Run, Workspace
from nfactory_core.models.auth import AuthSession, LoginAttempt
from nfactory_core.models.base import utcnow
from nfactory_core.retention import cutoff, retention_policy
from nfactory_core.states import TERMINAL_STATES

log = logging.getLogger("nfactory.worker")

Sessions = async_sessionmaker[AsyncSession]

RUN_FOLDER = re.compile(r"^run_[A-Za-z0-9_-]+$")
# Children first; LangGraph creates them at worker startup, so a fresh database may lack them.
CHECKPOINT_TABLES = ("checkpoint_writes", "checkpoint_blobs", "checkpoints")
_BATCH = 500


@dataclass(frozen=True)
class PurgeReport:
    runs: int = 0
    audit_entries: int = 0
    sign_in_rows: int = 0  # ended SSO sessions and login attempts


@dataclass(frozen=True)
class SweepReport:
    folders: int = 0
    checkpoints: int = 0


async def _deleted(session: AsyncSession, statement: Executable) -> int:
    result = cast(CursorResult[Any], await session.execute(statement))
    return result.rowcount or 0


async def _purge_runs(session: AsyncSession, workspace_id: str, before: datetime | None) -> int:
    if before is None:
        return 0
    expired = (
        select(Run.id)
        .join(Project, Project.id == Run.project_id)
        .where(
            Project.workspace_id == workspace_id,
            Run.state.in_([state.value for state in TERMINAL_STATES]),
            func.coalesce(Run.finished_at, Run.created_at) < before,
        )
    )
    ids = list(await session.scalars(expired))
    for start in range(0, len(ids), _BATCH):
        batch = ids[start : start + _BATCH]
        # Deliverables only lose their run on its deletion (SET NULL): delete them first.
        await session.execute(delete(Artifact).where(Artifact.run_id.in_(batch)))
        await session.execute(delete(Run).where(Run.id.in_(batch)))  # steps, events cascade
    return len(ids)


async def _purge_audit(session: AsyncSession, workspace_id: str, before: datetime | None) -> int:
    if before is None:
        return 0
    return await _deleted(
        session,
        delete(AuditLog).where(AuditLog.workspace_id == workspace_id, AuditLog.timestamp < before),
    )


async def _purge_sign_in(session: AsyncSession, now: datetime) -> int:
    ended = or_(AuthSession.expires_at < now, AuthSession.revoked_at.is_not(None))
    sessions = await _deleted(session, delete(AuthSession).where(ended))
    attempts = await _deleted(session, delete(LoginAttempt).where(LoginAttempt.expires_at < now))
    return sessions + attempts


async def purge_expired(sessions: Sessions, *, now: datetime | None = None) -> PurgeReport:
    now = now or utcnow()
    runs = audit_entries = 0
    async with sessions() as session:
        workspaces = (await session.execute(select(Workspace.id, Workspace.data_policy))).all()
        for workspace_id, data_policy in workspaces:
            policy = retention_policy(data_policy)
            purged_runs = await _purge_runs(session, workspace_id, cutoff(now, policy.runs_days))
            purged_audit = await _purge_audit(session, workspace_id, cutoff(now, policy.audit_days))
            if purged_runs or purged_audit:
                session.add(
                    AuditLog(
                        workspace_id=workspace_id,
                        actor_id=None,
                        action="retention.purge",
                        target=workspace_id,
                        decision="applied",
                        redacted_details={"runs": purged_runs, "audit_entries": purged_audit},
                    )
                )
            runs += purged_runs
            audit_entries += purged_audit
        sign_in_rows = await _purge_sign_in(session, now)
        await session.commit()
    return PurgeReport(runs=runs, audit_entries=audit_entries, sign_in_rows=sign_in_rows)


def _run_folders(roots: Sequence[Path]) -> dict[str, list[Path]]:
    """`run_*` folders under each root. Links are skipped: generated code may plant one."""
    found: dict[str, list[Path]] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for entry in root.iterdir():
            if entry.is_symlink() or entry.is_junction() or not entry.is_dir():
                continue
            if RUN_FOLDER.fullmatch(entry.name):
                found.setdefault(entry.name, []).append(entry)
    return found


async def _sweep_checkpoints(session: AsyncSession) -> int:
    removed = 0
    for table in CHECKPOINT_TABLES:
        if await session.scalar(text("SELECT to_regclass(:name)"), {"name": table}) is None:
            continue
        # The table name comes from the constant above, never from input.
        orphans = f"DELETE FROM {table} WHERE thread_id NOT IN (SELECT id FROM runs)"  # noqa: S608
        removed += await _deleted(session, text(orphans))
    return removed


async def sweep_orphans(sessions: Sessions, roots: Sequence[Path]) -> SweepReport:
    folders = _run_folders(roots)
    async with sessions() as session:
        existing = (
            set(await session.scalars(select(Run.id).where(Run.id.in_(list(folders)))))
            if folders
            else set()
        )
        checkpoints = await _sweep_checkpoints(session)
        await session.commit()
    removed = 0
    for run_id, paths in folders.items():
        if run_id in existing:
            continue
        for path in paths:
            shutil.rmtree(path, ignore_errors=True)
            removed += not path.exists()
    return SweepReport(folders=removed, checkpoints=checkpoints)


async def apply_retention(
    sessions: Sessions, settings: Settings
) -> tuple[PurgeReport, SweepReport]:
    purge = await purge_expired(sessions)
    roots = [Path(settings.artifact_root), Path(settings.workspace_root)]
    sweep = await sweep_orphans(sessions, roots)
    log.info(
        "retention: %d runs, %d audit entries, %d sign-in rows, %d folders, %d checkpoints",
        purge.runs,
        purge.audit_entries,
        purge.sign_in_rows,
        sweep.folders,
        sweep.checkpoints,
    )
    return purge, sweep
