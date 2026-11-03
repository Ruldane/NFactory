from nfactory_core.pipeline import PIPELINE_STEPS, step_names


def test_pipeline_follows_spec_order() -> None:
    assert step_names() == (
        "requirements",
        "plan",
        "architect",
        "build",
        "checks",
        "tests",
        "review",
        "docs",
        "package",
    )


def test_every_step_has_an_agent_role() -> None:
    assert all(role for _, role in PIPELINE_STEPS)
