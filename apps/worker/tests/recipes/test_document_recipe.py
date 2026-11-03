"""The document recipe produces a real .docx whose structure is verified."""

import json

from docx import Document

from nfactory_worker.brief import Brief, SectionSpec
from nfactory_worker.recipes.document import DocumentRecipe

PROCEDURE = Brief(
    title="Procédure de redémarrage du serveur de fichiers",
    summary="Redémarrer FS01 sans perte de données, hors heures ouvrées.",
    project_type="document",
    document_kind="procedure",
)


def test_without_sections_the_outline_of_the_kind_is_used() -> None:
    rendered = DocumentRecipe().render(PROCEDURE)
    outline = json.loads(rendered.files["content/outline.json"])
    assert outline["sections"] == [
        "Objet",
        "Périmètre",
        "Prérequis",
        "Étapes",
        "Vérification",
        "Retour arrière",
        "Contacts",
    ]
    assert rendered.deliverables == ("output/procedure-de-redemarrage-du-serveur-de-fichiers.docx",)


def test_missing_content_is_marked_not_invented() -> None:
    markdown = DocumentRecipe().render(PROCEDURE).files["content/document.md"]
    assert isinstance(markdown, str)
    assert markdown.count("À compléter") == 7


def test_brief_sections_are_used_as_given() -> None:
    brief = PROCEDURE.model_copy(
        update={"sections": [SectionSpec(title="Étapes", points=["Prévenir", "Arrêter"])]}
    )
    rendered = DocumentRecipe().render(brief)
    assert json.loads(rendered.files["content/outline.json"])["sections"] == ["Étapes"]


async def test_generated_docx_is_built_and_verified(run_recipe) -> None:  # type: ignore[no-untyped-def]
    brief = PROCEDURE.model_copy(
        update={
            "sections": [
                SectionSpec(title="Objet", points=["Redémarrer FS01 proprement."]),
                SectionSpec(title="Étapes", points=["Prévenir les utilisateurs", "Arrêter"]),
                SectionSpec(title="Contacts", points=[]),
            ]
        }
    )
    execution = await run_recipe(DocumentRecipe().render(brief))
    assert execution.failures() == []
    assert execution.report is not None and execution.report.ok

    path = execution.workspace.resolve(
        "output/procedure-de-redemarrage-du-serveur-de-fichiers.docx"
    )
    document = Document(str(path))
    headings = [p.text for p in document.paragraphs if p.style.name == "Heading 1"]
    assert headings == ["Objet", "Étapes", "Contacts"]
    assert document.core_properties.title == brief.title


async def test_hostile_text_cannot_break_the_structure(run_recipe) -> None:  # type: ignore[no-untyped-def]
    brief = PROCEDURE.model_copy(
        update={
            "title": "Titre\n## Section pirate",
            "sections": [SectionSpec(title="A\n# B", points=["- x\n## y", "{{z}}"])],
        }
    )
    execution = await run_recipe(DocumentRecipe().render(brief))
    assert execution.failures() == []
