"""Writes the demo catalog to the database.

Idempotent: every row has a fixed ID and is upserted, so re-running changes nothing.
"""

from datetime import datetime, timedelta

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.demo.catalog import DEMO_EPOCH, DEMO_PROJECTS, DemoProject, plan_steps
from app.services.identity import LOCAL_USER_ID, LOCAL_WORKSPACE_ID, ensure_local_identity
from nfactory_core.models import Approval, EventRecord, Project, Run, RunStep
from nfactory_core.states import TERMINAL_STATES, StepState


async def seed_demo(session: AsyncSession) -> None:
    # Demo projects live in the local workspace, flagged is_demo.
    await ensure_local_identity(session)
    for index, demo in enumerate(DEMO_PROJECTS):
        await _seed_project(session, demo, DEMO_EPOCH + timedelta(days=index))
    await session.commit()


async def _seed_project(session: AsyncSession, demo: DemoProject, created: datetime) -> None:
    project_id, run_id = f"proj_demo_{demo.slug}", f"run_demo_{demo.slug}"
    finished = created + timedelta(minutes=demo.duration_minutes)
    await session.merge(
        Project(
            id=project_id,
            workspace_id=LOCAL_WORKSPACE_ID,
            title=demo.title,
            description=demo.description,
            type=demo.type,
            template_id=demo.template,
            is_demo=True,
            created_at=created,
            updated_at=created,
        )
    )
    await session.flush()
    await session.merge(
        Run(
            id=run_id,
            project_id=project_id,
            request=demo.description,
            state=demo.run_state.value,
            budget={"max_llm_calls": 80, "max_repair_attempts": 3},
            provider_config={"default": "fake_demo"},
            cost_estimate_usd=demo.cost_usd,
            error=demo.error,
            is_demo=True,
            created_at=created,
            started_at=created,
            finished_at=finished if demo.run_state in TERMINAL_STATES else None,
        )
    )
    await session.flush()

    clock = created
    for position, step in enumerate(plan_steps(demo.run_state, demo.type)):
        step_id = f"step_demo_{demo.slug}_{step.name}"
        ran = step.state in {StepState.SUCCEEDED, StepState.FAILED}
        ended = clock + timedelta(seconds=40 + 20 * position)
        await session.merge(
            RunStep(
                id=step_id,
                run_id=run_id,
                position=position,
                name=step.name,
                agent_role=step.role,
                state=step.state.value,
                attempts=step.attempts,
                started_at=clock if ran else None,
                ended_at=ended if ran else None,
                error=step.error,
                output=step.output,
            )
        )
        if ran:
            outcome = "completed" if step.state is StepState.SUCCEEDED else "failed"
            await _insert_event(
                session,
                f"evt_{demo.slug}_{step.name}_start",
                run_id,
                step_id,
                "step.started",
                clock,
                {"agent": step.role},
            )
            await _insert_event(
                session,
                f"evt_{demo.slug}_{step.name}_end",
                run_id,
                step_id,
                f"step.{outcome}",
                ended,
                {"agent": step.role, "attempts": step.attempts},
            )
            clock = ended

    if demo.approval_summary:
        await session.merge(
            Approval(
                id=f"apr_demo_{demo.slug}",
                run_id=run_id,
                action_type="plan",
                summary=demo.approval_summary,
                details={"risk": "medium"},
                requester_id=LOCAL_USER_ID,
                created_at=clock,
            )
        )


async def _insert_event(
    session: AsyncSession,
    event_id: str,
    run_id: str,
    step_id: str,
    type_: str,
    at: datetime,
    payload: dict[str, object],
) -> None:
    # `seq` is the primary key, so upsert on the unique business ID instead.
    statement = (
        insert(EventRecord)
        .values(
            id=event_id,
            run_id=run_id,
            step_id=step_id,
            type=type_,
            schema_version="1",
            payload_redacted=payload,
            created_at=at,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    await session.execute(statement)
