"""The engines of one run: the LLM each agent role talks to, frozen at launch.

A missing role is an error, never a reason to borrow another role's engine.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from nfactory_core.routing import ROLES
from nfactory_worker.agents.base import LLM

Fallback = Literal["ask_user", "none"]


@dataclass(frozen=True)
class Engines:
    llms: Mapping[str, LLM]
    fallback: Fallback = "none"

    @classmethod
    def single(cls, llm: LLM, fallback: Fallback = "none") -> "Engines":
        return cls({role: llm for role in ROLES}, fallback)

    def for_role(self, role: str) -> LLM:
        llm = self.llms.get(role)
        if llm is None:
            raise LookupError(f"Aucun moteur IA pour le rôle « {role} » dans ce run.")
        return llm
