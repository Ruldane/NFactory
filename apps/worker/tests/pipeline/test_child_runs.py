"""Scenario E (spec §3.5, task 3.11): a change request on a delivered project starts from
the delivered brief, rebuilds, is validated again by the real checks and tests, and
shows what changed as a diff."""

from dataclasses import replace
from pathlib import Path

from nfactory_worker.pipeline import ParentRun, execute_run


async def deliver(harness, run_id: str, request: str, parent: ParentRun | None = None):  # type: ignore[no-untyped-def]
    run = replace(
        harness.input("api", "python-api", request, title="Annuaire"), run_id=run_id, parent=parent
    )
    return await execute_run(harness.deps(), run)


async def test_a_change_request_rebuilds_from_the_delivered_brief(harness) -> None:  # type: ignore[no-untyped-def]
    first = await deliver(harness, "run_parent", "Une API d'annuaire des contacts")
    assert first.outcome == "COMPLETED"
    delivered = harness.reporter.outputs["requirements"]["brief"]

    child = await deliver(
        harness,
        "run_child",
        "Ajoute un filtre par département",
        ParentRun(run_id="run_parent", brief=delivered),
    )

    assert child.outcome == "COMPLETED", child.error
    brief = harness.reporter.outputs["requirements"]["brief"]
    names = [f["name"] for f in brief["entity"]["fields"]]
    assert names == [*(f["name"] for f in delivered["entity"]["fields"]), "departement"]
    assert brief["entity"]["plural"] == delivered["entity"]["plural"]
    # A new validation: the real tests ran again on the changed project.
    report = harness.reporter.outputs["tests"]["report"]
    assert report["passed"] >= 8 and report["failed"] == 0

    changes = harness.reporter.outputs["package"]["changes"]
    assert changes["parent_run_id"] == "run_parent"
    assert changes["added"] == [] and changes["removed"] == []
    assert "app/models.py" in changes["modified"]
    diff = next(a for a in harness.reporter.artifacts if a.filename == "modifications.diff")
    assert diff.mime == "text/x-diff"
    patch = Path(diff.path).read_text(encoding="utf-8")  # noqa: ASYNC240 - test check
    assert "+++ b/app/models.py" in patch and "departement" in patch
    (event,) = harness.events("changes.computed")
    assert event["parent_run_id"] == "run_parent" and event["modified"] == len(changes["modified"])


async def test_the_child_keeps_the_delivered_table(harness) -> None:  # type: ignore[no-untyped-def]
    await deliver(harness, "run_parent", "Une API d'annuaire des contacts")
    delivered = harness.reporter.outputs["requirements"]["brief"]
    renamed = {**delivered, "entity": {**delivered["entity"], "name": "x", "plural": "xs"}}

    # The delivered table name and route carry over to the child, whatever they are.
    await deliver(harness, "run_child", "Ajoute un champ note", ParentRun("run_parent", renamed))

    entity = harness.reporter.outputs["requirements"]["brief"]["entity"]
    assert (entity["name"], entity["plural"]) == ("x", "xs")


async def test_a_first_run_has_no_changes(harness) -> None:  # type: ignore[no-untyped-def]
    await deliver(harness, "run_parent", "Une API d'annuaire des contacts")

    assert "changes" not in harness.reporter.outputs["package"]
    assert harness.events("changes.computed") == []


async def test_a_parent_whose_workspace_is_gone_is_said(harness) -> None:  # type: ignore[no-untyped-def]
    await deliver(harness, "run_parent", "Une API d'annuaire des contacts")
    delivered = harness.reporter.outputs["requirements"]["brief"]

    result = await deliver(
        harness, "run_child", "Ajoute un champ note", ParentRun("run_missing", delivered)
    )

    assert result.outcome == "COMPLETED"
    changes = harness.reporter.outputs["package"]["changes"]
    assert changes == {"parent_run_id": "run_missing", "available": False}
