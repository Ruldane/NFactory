"""Run guardrails (task 1.3/1.4): LLM-call budget, step limit, trace id on agent output."""

from nfactory_worker.pipeline import execute_run

# A complete demo run calls 6 agents: requirements, plan, architect, review, docs
# (+ debug only on failure). Package, build and checks call none.
AGENT_STEPS = ["requirements", "plan", "architect", "review", "docs"]


async def test_run_stops_when_its_llm_budget_is_spent(harness) -> None:  # type: ignore[no-untyped-def]
    run = harness.input("api", "python-api", "API des licences")

    result = await execute_run(harness.deps(max_llm_calls=3), run)

    assert result.outcome == "FAILED"
    assert "Budget" in (result.error or "")
    assert "3" in (result.error or "")
    # The 4th agent call was refused before reaching the model.
    assert len(harness.events("agent.progress")) == 3
    assert harness.reporter.failed["review"]


async def test_budget_large_enough_lets_the_run_complete(harness) -> None:  # type: ignore[no-untyped-def]
    run = harness.input("document", "document", "Note de cadrage")

    result = await execute_run(harness.deps(max_llm_calls=len(AGENT_STEPS)), run)

    assert result.outcome == "COMPLETED"


async def test_run_stops_at_the_step_limit(harness) -> None:  # type: ignore[no-untyped-def]
    run = harness.input("document", "document", "Note de cadrage")

    result = await execute_run(harness.deps(max_steps=4), run)

    assert result.outcome == "FAILED"
    assert "4" in (result.error or "") and "étapes" in (result.error or "")
    assert "package" not in harness.reporter.started


async def test_every_agent_output_carries_the_run_trace_id(harness) -> None:  # type: ignore[no-untyped-def]
    run = harness.input("excel", "excel-automation", "Rapport des heures", trace_id="abc123")

    await execute_run(harness.deps(), run)

    progress = harness.events("agent.progress")
    assert progress and {event["trace_id"] for event in progress} == {"abc123"}
    assert harness.reporter.outputs["requirements"]["agent"]["trace_id"] == "abc123"
