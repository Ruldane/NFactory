"""Chunking keeps sections, symbols and the original line numbers (task 3.2)."""

import itertools

from nfactory_core.knowledge import Extracted, chunk, extract

GUIDE = """# Installation

Lancer `docker compose up`.

## Prérequis

Docker Desktop doit tourner.

# Dépannage

Relancer le service.
"""

CODE = '''"""Module de licences."""

import datetime


def expire_soon(licence, days=30):
    """Vrai si la licence expire bientôt."""
    return licence.end - datetime.date.today() < datetime.timedelta(days=days)


@dataclass
class Licence:
    name: str
    end: datetime.date
'''


def _lines(text: str, start: int, end: int) -> str:
    return "\n".join(text.splitlines()[start - 1 : end])


def test_markdown_is_cut_by_section_with_exact_lines() -> None:
    chunks = chunk(extract("guide.md", GUIDE.encode()))

    assert [c.section for c in chunks] == [
        "Installation",
        "Installation > Prérequis",
        "Dépannage",
    ]
    for c in chunks:
        assert c.content == _lines(GUIDE, c.start_line, c.end_line).strip()
    assert chunks[2].start_line == 9


def test_python_is_cut_by_function_and_class() -> None:
    chunks = chunk(extract("licences.py", CODE.encode()))

    by_symbol = {c.symbol: c for c in chunks}
    assert {"expire_soon", "Licence"} <= set(by_symbol)
    assert by_symbol["Licence"].content.startswith("@dataclass")  # decorators included
    assert by_symbol["expire_soon"].start_line == 6
    assert "import datetime" in by_symbol[None].content  # module-level code kept


def test_long_sections_are_windowed_with_overlap() -> None:
    body = "\n".join(f"Ligne {i} du paragraphe long." for i in range(1, 301))
    chunks = chunk(extract("long.md", f"# Long\n{body}\n".encode()), max_chars=1000)

    assert len(chunks) > 3
    assert all(len(c.content) <= 1000 for c in chunks)
    for previous, current in itertools.pairwise(chunks):
        assert current.start_line == previous.end_line - 1  # 2 lines shared
    assert chunks[-1].end_line == 301


def test_pdf_chunks_know_their_page_and_never_span_two() -> None:
    pdf = Extracted(kind="pdf", text="Page un.\nSuite.\nPage deux.\n", page_starts=(1, 3))
    chunks = chunk(pdf)

    assert [(c.page, c.start_line, c.end_line) for c in chunks] == [(1, 1, 2), (2, 3, 3)]


def test_other_code_finds_a_symbol_per_block() -> None:
    script = (
        "function Get-Licence {\n    param($Name)\n}\n\n"
        "function Set-Licence {\n    param($Name)\n}\n"
    )
    chunks = chunk(extract("licences.ps1", script.encode()), max_chars=60)

    assert [c.symbol for c in chunks] == ["Get-Licence", "Set-Licence"]


def test_chunks_are_numbered_in_order() -> None:
    chunks = chunk(extract("guide.md", GUIDE.encode()))

    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
