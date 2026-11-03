"""Demo mode: every agent gets a valid, deterministic answer derived from its input."""

from nfactory_worker.agents import (
    ARCHITECT,
    DEBUGGER,
    DOCUMENTER,
    PLANNER,
    REQUIREMENTS,
    REVIEWER,
    demo_llm,
)
from nfactory_worker.brief import Brief


async def brief_for(request: str, project_type: str, title: str = "Projet") -> Brief:
    payload = {"request": request, "project_type": project_type, "title": title}
    return (await REQUIREMENTS.run(demo_llm(), payload)).output


async def test_api_request_picks_a_matching_domain_entity() -> None:
    brief = await brief_for("Une API pour l'inventaire du matériel informatique", "api")
    assert brief.entity is not None
    assert brief.entity.plural == "equipements"


async def test_a_webapp_request_picks_its_domain_entity_too() -> None:
    brief = await brief_for("Application de suivi des licences, export Excel", "webapp")
    assert brief.entity is not None
    assert brief.entity.plural == "licences"
    assert [f.label for f in brief.entity.fields][:2] == ["Logiciel", "Éditeur"]


async def test_unknown_domain_falls_back_to_a_generic_entity() -> None:
    brief = await brief_for("Une API pour gérer des trucs", "api")
    assert brief.entity is not None and brief.entity.plural == "items"


async def test_document_kind_is_detected_from_the_request() -> None:
    assert (await brief_for("Procédure de redémarrage du NAS", "document")).document_kind == (
        "procedure"
    )
    assert (await brief_for("Rapport d'audit des sauvegardes", "document")).document_kind == (
        "report"
    )
    assert (await brief_for("Proposition de migration", "document")).document_kind == "note"


async def test_document_brief_keeps_the_request_and_marks_the_rest() -> None:
    brief = await brief_for("Procédure de redémarrage du NAS. Prévenir le support.", "document")
    assert brief.sections[0].points  # first section carries the request
    assert any(not section.points for section in brief.sections)  # rest left to complete


async def test_same_input_same_brief() -> None:
    a = await brief_for("API des licences logicielles", "api", "Licences")
    b = await brief_for("API des licences logicielles", "api", "Licences")
    assert a == b


async def test_every_agent_answers_with_a_valid_output() -> None:
    brief = await brief_for("API des licences logicielles", "api", "Licences")
    llm = demo_llm()
    plan = await PLANNER.run(llm, {"brief": brief.model_dump(), "recipe": "python-api"})
    assert plan.output.tasks
    architecture = await ARCHITECT.run(llm, {"brief": brief.model_dump(), "recipe": "python-api"})
    assert architecture.output.components
    checks = [{"name": "Tests (pytest)", "ok": True, "detail": ""}]
    review = await REVIEWER.run(llm, {"recipe": "python-api", "checks": checks})
    assert review.output.verdict == "approve"
    failing = [{"name": "Tests (pytest)", "ok": False, "detail": "assert 1 == 2"}]
    assert (
        await REVIEWER.run(llm, {"recipe": "python-api", "checks": failing})
    ).output.verdict == ("changes_requested")
    debug = await DEBUGGER.run(llm, {"failures": ["assert 1 == 2"], "files": ["app/main.py"]})
    assert debug.output.patches == []  # demo mode never pretends to fix code
    docs = await DOCUMENTER.run(
        llm,
        {
            "brief": brief.model_dump(),
            "recipe": "python-api",
            "deliverables": [],
            "files": ["app/main.py"],
            "checks": checks,
        },
    )
    assert docs.output.summary and docs.output.verify


async def change_of(previous: Brief, request: str) -> Brief:
    payload = {
        "request": request,
        "project_type": previous.project_type,
        "title": previous.title,
        "previous_brief": previous.model_dump(mode="json"),
    }
    return (await REQUIREMENTS.run(demo_llm(), payload)).output


async def test_a_change_request_keeps_the_delivered_brief_and_adds_the_field() -> None:
    previous = await brief_for("Une API d'annuaire des contacts", "api", "Annuaire")

    changed = await change_of(previous, "Ajoute un filtre par département et un export PDF")

    assert changed.entity is not None and previous.entity is not None
    assert changed.entity.plural == previous.entity.plural
    assert changed.entity.fields[: len(previous.entity.fields)] == previous.entity.fields
    added = changed.entity.fields[-1]
    assert (added.name, added.label, added.type) == ("departement", "Département", "str")
    assert previous.goals[0] in changed.goals
    # What the demo cannot honour is said, never silently dropped.
    assert any("export PDF" in q for q in changed.open_questions)


async def test_a_change_on_a_brief_without_entity_starts_from_the_default_one() -> None:
    delivered = await brief_for("Gestion des licences logicielles", "webapp", "Licences")
    previous = delivered.model_copy(update={"entity": None})

    changed = await change_of(previous, "Ajoute le champ éditeur")

    assert changed.entity is not None
    assert changed.entity.plural == "items"
    assert [f.name for f in changed.entity.fields] == ["name", "description", "editeur"]


async def test_a_field_already_present_is_not_added_twice() -> None:
    previous = await brief_for("Une API d'annuaire des contacts", "api")

    changed = await change_of(previous, "Ajoute un champ ville")

    assert changed.entity is not None and previous.entity is not None
    assert [f.name for f in changed.entity.fields] == [f.name for f in previous.entity.fields]
