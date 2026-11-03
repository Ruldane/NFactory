"""The factory pipeline. Interface: execute_run(deps, run, checkpointer=None) -> RunResult.

Ports (Reporter, RunControl, Knowledge) are implemented by the worker job (database) and by
pipeline.memory (tests).
"""

from nfactory_worker.pipeline.execute import execute_run
from nfactory_worker.pipeline.memory import MemoryControl, MemoryKnowledge, MemoryReporter
from nfactory_worker.pipeline.ports import Knowledge, Reporter, Retrieval, RunControl
from nfactory_worker.pipeline.types import ParentRun, PipelineDeps, RunInput, RunResult

__all__ = [
    "Knowledge",
    "MemoryControl",
    "MemoryKnowledge",
    "MemoryReporter",
    "ParentRun",
    "PipelineDeps",
    "Reporter",
    "Retrieval",
    "RunControl",
    "RunInput",
    "RunResult",
    "execute_run",
]
