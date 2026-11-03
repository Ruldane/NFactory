from nfactory_core.pipeline import step_names
from nfactory_core.roster import AGENTS, plan_steps
from nfactory_core.routing import ROLES


def test_the_ten_roles_of_the_spec_are_listed_once() -> None:
    codes = [agent.code for agent in AGENTS if agent.code]
    assert codes == [f"A{n}" for n in range(1, 11)]
    assert len({agent.role for agent in AGENTS}) == len(AGENTS)


def test_orchestration_testing_and_permissions_are_code_not_prompts() -> None:
    kinds = {agent.code: agent.kind for agent in AGENTS}
    assert kinds["A4"] == "code"
    assert kinds["A7"] == "code"
    assert kinds["A10"] == "code"


def test_only_model_roles_can_be_routed_to_an_engine() -> None:
    model_roles = {agent.role for agent in AGENTS if agent.kind == "model"}
    assert model_roles == set(ROLES)


def test_an_excel_run_does_not_call_the_architect() -> None:
    plan = {step.name: step for step in plan_steps("excel")}

    assert not plan["architect"].active
    assert plan["architect"].reason
    assert plan["build"].role == "automation"


def test_an_application_gets_an_architect_and_a_builder() -> None:
    for project_type in ("webapp", "api"):
        plan = {step.name: step for step in plan_steps(project_type)}
        assert plan["architect"].active
        assert plan["build"].role == "builder"


def test_every_plan_keeps_the_pipeline_order() -> None:
    for project_type in ("webapp", "api", "excel", "document", "powershell"):
        assert tuple(step.name for step in plan_steps(project_type)) == step_names()


def test_the_dashboard_knows_every_role() -> None:
    import re
    from pathlib import Path

    source = Path(__file__).parents[3] / "apps/dashboard/lib/agents.ts"
    block = source.read_text(encoding="utf-8").split("AGENTS: Record<string, AgentInfo> = {", 1)[1]
    entries = re.findall(r'^  (\w+): \{ code: (null|"A\d+"), label: "([^"]+)"', block, re.M)
    assert {
        role: (None if code == "null" else code.strip('"'), label) for role, code, label in entries
    } == {agent.role: (agent.code, agent.label) for agent in AGENTS}
