import pytest

from nfactory_worker.recipes.rendering import TemplateError, py_literal, render_template


def test_placeholders_are_replaced() -> None:
    assert render_template("x = {{a}} + {{b}}", {"a": "1", "b": "2"}) == "x = 1 + 2"


def test_python_braces_are_left_alone() -> None:
    assert render_template('d = {"k": {{v}}}', {"v": "1"}) == 'd = {"k": 1}'


def test_missing_value_fails_loudly() -> None:
    with pytest.raises(TemplateError, match="b"):
        render_template("{{a}} {{b}}", {"a": "1"})


def test_unused_value_fails_loudly() -> None:
    # Catches typos in either the template or the recipe.
    with pytest.raises(TemplateError, match="c"):
        render_template("{{a}}", {"a": "1", "c": "2"})


def test_py_literal_neutralises_injection() -> None:
    hostile = 'x"); import os; os.system("rm -rf /") #\n'
    literal = py_literal(hostile)
    assert eval(literal) == hostile


def test_powershell_literals_stay_inert() -> None:
    from nfactory_worker.recipes.rendering import ps_literal

    # PowerShell also treats typographic single quotes as quote characters.
    assert ps_literal("l'été") == "'l''été'"
    assert ps_literal("a\u2018b\u2019c") == "'a\u2018\u2018b\u2019\u2019c'"
    assert ps_literal(r"$(Remove-Item C:\)") == r"'$(Remove-Item C:\)'"


def test_powershell_comments_cannot_be_closed_from_the_brief() -> None:
    from nfactory_worker.recipes.rendering import ps_comment

    assert (
        ps_comment("Rapport #> Remove-Item x <# fin\nligne")
        == "Rapport # > Remove-Item x < # fin ligne"
    )
