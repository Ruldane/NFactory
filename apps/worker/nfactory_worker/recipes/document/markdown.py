"""Render the document's Markdown source from a brief.

Every piece of brief text is flattened to one line, so it can never open a new heading
or list item. Missing content is marked "À compléter", never invented.
"""

from dataclasses import dataclass

from nfactory_worker.brief import Brief
from nfactory_worker.recipes.document.outlines import OUTLINES

TODO_MARK = "À compléter"


@dataclass(frozen=True)
class Section:
    title: str
    points: tuple[str, ...]
    hint: str  # what belongs here, used when there are no points


def one_line(text: str) -> str:
    return " ".join(text.split()) or "Sans titre"


def sections_for(brief: Brief) -> list[Section]:
    hints = dict(OUTLINES[brief.document_kind])
    if brief.sections:
        return [
            Section(
                title=one_line(s.title),
                points=tuple(one_line(p) for p in s.points if p.strip()),
                hint=hints.get(s.title, "contenu de cette section"),
            )
            for s in brief.sections
        ]
    return [Section(title=t, points=(), hint=h) for t, h in OUTLINES[brief.document_kind]]


def render_markdown(title: str, summary: str, sections: list[Section]) -> str:
    lines = [f"# {title}", ""]
    if summary.strip():
        lines += [f"> {one_line(summary)}", ""]
    for section in sections:
        lines += [f"## {section.title}", ""]
        if section.points:
            lines += [f"- {point}" for point in section.points]
        else:
            lines.append(f"_{TODO_MARK} : {section.hint}._")
        lines.append("")
    return "\n".join(lines)
