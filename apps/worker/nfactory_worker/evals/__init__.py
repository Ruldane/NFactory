"""Evals (task 5.3, spec §14.2): versioned scenarios run through the real pipeline,
scored by deterministic checks, reported as JSON and HTML with each figure's source.

Interface: load_cases, suite_counts, Case, Expect, CaseError; EvalEnv, run_case;
score, Check; build_report, write_report, render_html.
"""

from nfactory_worker.evals.cases import Case, CaseError, Expect, load_cases, suite_counts
from nfactory_worker.evals.checks import Check, score
from nfactory_worker.evals.report import build_report, render_html, write_report
from nfactory_worker.evals.run import CaseRun, EvalEnv, run_case

__all__ = [
    "Case",
    "CaseError",
    "CaseRun",
    "Check",
    "EvalEnv",
    "Expect",
    "build_report",
    "load_cases",
    "render_html",
    "run_case",
    "score",
    "suite_counts",
    "write_report",
]
