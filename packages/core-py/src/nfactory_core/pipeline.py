"""Ordered steps of a factory run (spec §5.2). Shared by the API (creates the step rows)
and the worker (executes them)."""

# (step name, agent role)
PIPELINE_STEPS: tuple[tuple[str, str], ...] = (
    ("requirements", "requirements"),
    ("plan", "planner"),
    ("architect", "architect"),
    ("build", "builder"),
    ("checks", "tester"),
    ("tests", "tester"),
    ("review", "reviewer"),
    ("docs", "documenter"),
    ("package", "security_delivery"),
)


def step_names() -> tuple[str, ...]:
    return tuple(name for name, _ in PIPELINE_STEPS)


# The ARQ queue and job the API enqueues and the worker consumes.
RUN_QUEUE = "factory-runs"
RUN_JOB = "run_factory"
# Computes missing knowledge vectors of one workspace (ADR-0007).
INDEX_JOB = "index_knowledge"
# Tests a coding agent's change in the sandbox (task 4.4).
AGENT_CHECK_JOB = "check_agent_task"
