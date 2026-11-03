"""checks and tests steps: run the recipe's commands and read verified results.

A failing check does not fail the step yet: it hands over to the repair loop by
setting `failed_step`. Only the repair node gives up. The checks step starts with the
deterministic secret scan (A10): a finding is a failure like any other.
"""

from dataclasses import asdict
from typing import Any

from nfactory_worker.pipeline.nodes.common import Update, checks_of, workspace_of
from nfactory_worker.pipeline.types import FactoryState, PipelineDeps
from nfactory_worker.recipes import Check, Stage
from nfactory_worker.runner import JUnitError, TestReport, merge_reports, parse_junit
from nfactory_worker.security import scan_files

_DETAIL_CHARS = 1500
LEAK_SCAN = "Recherche de secrets"


async def checks(state: FactoryState, deps: PipelineDeps) -> Update:
    return await _run_stages(state, deps, "checks", ("static", "build"), scan=True)


async def tests(state: FactoryState, deps: PipelineDeps) -> Update:
    return await _run_stages(state, deps, "tests", ("tests",))


async def _run_stages(
    state: FactoryState,
    deps: PipelineDeps,
    step: str,
    stages: tuple[Stage, ...],
    *,
    scan: bool = False,
) -> Update:
    selected = [check for check in checks_of(state) if check.stage in stages]
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    reports: list[TestReport] = []
    if scan:  # secrets first: nothing is built or run on top of a leak
        result, failure = await _scan_secrets(state, deps, step)
        results.append(result)
        if failure:
            failures.append(failure)
            selected = []
    for check in selected:
        result, check_report, failure = await _run_one(state, deps, step, check)
        results.append(result)
        if check_report is not None:
            reports.append(check_report)
        if failure:
            failures.append(failure)
            break  # later checks depend on earlier ones (build before tests)
    if step == "tests" and not selected:
        failures.append("Aucun test défini pour cette recette.")

    all_results = {**state.get("results", {}), step: results}
    output: dict[str, Any] = {"checks": results}
    if reports:
        output["report"] = _as_dict(merge_reports(reports))  # backend + frontend add up
    repairs = [r for r in state.get("repair_log", []) if r.get("step") == step]
    if repairs:
        output["repairs"] = repairs  # shown in the timeline under this step
    if failures:
        return {"results": all_results, "failed_step": step, "failures": failures, "output": output}
    return {"results": all_results, "failed_step": None, "failures": [], "output": output}


async def _run_one(
    state: FactoryState, deps: PipelineDeps, step: str, check: Check
) -> tuple[dict[str, Any], TestReport | None, str | None]:
    result = await deps.runner.run(state["run_id"], check.argv, check.timeout_s)
    await deps.reporter.emit(
        "tool.invoked",
        {
            "check": check.name,
            "argv": list(check.argv),
            "exit_code": result.exit_code,
            "duration_s": round(result.duration_s, 3),
            "timed_out": result.timed_out,
        },
        step,
    )
    detail = (result.stdout + "\n" + result.stderr).strip()[-_DETAIL_CHARS:]
    ok = result.ok
    report = None
    failure = None
    if check.junit_path:
        try:
            parsed = parse_junit(workspace_of(deps, state).read_text(check.junit_path))
        except (OSError, JUnitError) as exc:
            ok = False
            detail = f"Rapport de tests illisible ({exc}).\n{detail}"
        else:
            report = parsed
            ok = ok and parsed.ok
            kind = "test.passed" if parsed.ok else "test.failed"
            await deps.reporter.emit(kind, _as_dict(parsed), step)
            if parsed.failures:
                detail = "\n".join(f"{f.name}: {f.message}" for f in parsed.failures)
    if result.timed_out:
        detail = f"Délai dépassé ({check.timeout_s} s).\n{detail}"
    if not ok:
        failure = f"{check.name} : {detail or f'code de sortie {result.exit_code}'}"
    summary = {"name": check.name, "stage": check.stage, "ok": ok, "detail": detail[-500:]}
    return summary, report, failure


async def _scan_secrets(
    state: FactoryState, deps: PipelineDeps, step: str
) -> tuple[dict[str, Any], str | None]:
    workspace = workspace_of(deps, state)
    files = {path: workspace.read_bytes(path) for path in workspace.files()}
    findings = scan_files(files)
    messages = [finding.message for finding in findings]
    await deps.reporter.emit(
        "security.scanned",
        {"files": len(files), "findings": len(findings), "locations": messages[:20]},
        step,
    )
    detail = "\n".join(messages[:20])
    summary = {"name": LEAK_SCAN, "stage": "static", "ok": not findings, "detail": detail[-500:]}
    if not findings:
        return summary, None
    return (
        summary,
        f"{LEAK_SCAN} : retirer ces secrets du code (variables d'environnement).\n{detail}",
    )


def _as_dict(report: TestReport) -> dict[str, Any]:
    return asdict(report) | {"total": report.total, "ok": report.ok}
