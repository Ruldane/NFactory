"""Database adapters for the pipeline ports: step rows, the event log, artifacts and
cancellation. Each call uses its own short transaction so readers (SSE, dashboard)
see progress immediately."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nfactory_core.events import Notifier, record_event
from nfactory_core.events.redaction import redact
from nfactory_core.models import Artifact, Run, RunStep
from nfactory_core.states import RunState, StepState
from nfactory_worker.artifacts import StoredArtifact

Sessions = async_sessionmaker[AsyncSession]
StepHook = Callable[[str], Awaitable[None]]


class DatabaseReporter:
    def __init__(
        self,
        sessions: Sessions,
        run_id: str,
        project_id: str,
        notify: Notifier | None = None,
        after_step: StepHook | None = None,
    ) -> None:
        self._sessions = sessions
        self._run_id = run_id
        self._project_id = project_id
        self._notify = notify
        self._after_step = after_step

    async def step_started(self, step: str) -> None:
        step_id = await self._update_step(
            step,
            state=StepState.RUNNING,
            started_at=_now(),
            ended_at=None,
            error=None,
            increment=True,
        )
        await self.emit("step.started", {"step": step}, step, step_id=step_id)

    async def step_succeeded(self, step: str, output: dict[str, Any]) -> None:
        step_id = await self._update_step(
            step, state=StepState.SUCCEEDED, ended_at=_now(), output=redact(output)
        )
        await self.emit("step.completed", {"step": step}, step, step_id=step_id)
        if self._after_step is not None:
            await self._after_step(step)

    async def step_failed(
        self, step: str, error: str, output: dict[str, Any] | None = None
    ) -> None:
        extra = {"output": redact(output)} if output else {}
        step_id = await self._update_step(
            step, state=StepState.FAILED, ended_at=_now(), error=error, **extra
        )
        await self.emit("step.failed", {"step": step, "error": error}, step, step_id=step_id)

    async def step_skipped(self, step: str, reason: str) -> None:
        step_id = await self._update_step(
            step, state=StepState.SKIPPED, ended_at=_now(), output={"skipped": reason}
        )
        await self.emit("step.skipped", {"step": step, "reason": reason}, step, step_id=step_id)

    async def emit(
        self,
        type: str,
        payload: dict[str, Any],
        step: str | None = None,
        *,
        step_id: str | None = None,
    ) -> None:
        if step is not None and step_id is None:
            step_id = await self._step_id(step)
        await record_event(self._sessions, self._run_id, type, payload, step_id, self._notify)

    async def artifact_saved(self, artifact: StoredArtifact) -> None:
        async with self._sessions() as session:
            existing = await session.scalar(
                select(Artifact).where(
                    Artifact.run_id == self._run_id, Artifact.filename == artifact.filename
                )
            )
            row = existing or Artifact(project_id=self._project_id, run_id=self._run_id)
            row.filename = artifact.filename
            row.mime = artifact.mime
            row.storage_key = artifact.storage_key
            row.checksum = artifact.checksum
            row.size = artifact.size
            session.add(row)
            await session.commit()

    async def _step_id(self, step: str) -> str | None:
        async with self._sessions() as session:
            return await session.scalar(
                select(RunStep.id).where(RunStep.run_id == self._run_id, RunStep.name == step)
            )

    async def _update_step(
        self, step: str, *, state: StepState, increment: bool = False, **values: Any
    ) -> str:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RunStep).where(RunStep.run_id == self._run_id, RunStep.name == step)
            )
            if row is None:
                raise LookupError(f"Unknown step {step!r} for run {self._run_id}")
            row.state = state.value
            if increment:
                row.attempts += 1
            for key, value in values.items():
                setattr(row, key, value)
            await session.commit()
            return row.id


class DatabaseControl:
    """The user cancels by setting the run to CANCELLED; the pipeline stops at the next step."""

    def __init__(self, sessions: Sessions, run_id: str) -> None:
        self._sessions = sessions
        self._run_id = run_id

    async def cancel_requested(self) -> bool:
        async with self._sessions() as session:
            state = await session.scalar(select(Run.state).where(Run.id == self._run_id))
        return state == RunState.CANCELLED.value


def _now() -> datetime:
    return datetime.now(UTC)
