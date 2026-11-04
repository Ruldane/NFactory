"""Documenter agent: the Explain mode (spec F, task 1.10) — a plain-language summary of
what was generated and what the user must check."""

from pydantic import BaseModel, Field

from nfactory_worker.agents.base import Agent


class Explanation(BaseModel):
    summary: str = Field(min_length=1)
    generated: list[str] = Field(default_factory=list)  # what is in the delivery
    verify: list[str] = Field(min_length=1)  # what a human must check before use
    limits: list[str] = Field(default_factory=list)


DOCUMENTER = Agent(
    name="documenter",
    prompt_version="1",
    instructions="""
You explain the delivery to a non-developer: what it does, what is inside, what they
must verify before using it, and its known limits. Short sentences, no jargon.
""",
    output_model=Explanation,
)


def explanation_markdown(title: str, explanation: Explanation, notice: str) -> str:
    """`notice` is the AI-generated statement, quoted under the title (ADR-0014)."""

    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {' '.join(item.split())}" for item in items) or "- Aucun"

    return (
        f"# Explication — {' '.join(title.split())}\n\n"
        f"> {notice}\n\n"
        f"{explanation.summary}\n\n"
        f"## Ce qui a été produit\n\n{bullets(explanation.generated)}\n\n"
        f"## À vérifier avant utilisation\n\n{bullets(explanation.verify)}\n\n"
        f"## Limites connues\n\n{bullets(explanation.limits)}\n"
    )
