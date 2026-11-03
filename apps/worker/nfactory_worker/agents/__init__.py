"""Agents, one module each. Interface: the agent instances, LLM, Engines, AgentResult,
demo_llm."""

from nfactory_worker.agents.architect import ARCHITECT, ArchitectureNote
from nfactory_worker.agents.base import LLM, Agent, AgentMeta, AgentOutputError, AgentResult
from nfactory_worker.agents.debugger import DEBUGGER, DebugAnalysis, FilePatch
from nfactory_worker.agents.demo import demo_llm
from nfactory_worker.agents.documenter import DOCUMENTER, Explanation, explanation_markdown
from nfactory_worker.agents.engines import Engines
from nfactory_worker.agents.planner import PLANNER, ExecutionPlan
from nfactory_worker.agents.requirements import REQUIREMENTS
from nfactory_worker.agents.reviewer import REVIEWER, Review

__all__ = [
    "ARCHITECT",
    "DEBUGGER",
    "DOCUMENTER",
    "LLM",
    "PLANNER",
    "REQUIREMENTS",
    "REVIEWER",
    "Agent",
    "AgentMeta",
    "AgentOutputError",
    "AgentResult",
    "ArchitectureNote",
    "DebugAnalysis",
    "Engines",
    "ExecutionPlan",
    "Explanation",
    "FilePatch",
    "Review",
    "demo_llm",
    "explanation_markdown",
]
