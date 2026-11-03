"""Run the eval scenarios and write the report (task 5.3).

    uv run python -m nfactory_worker.evals                  # local runner
    ./scripts/evals.ps1                                     # inside the sandbox
    ./scripts/evals.ps1 --engine demo --engine openai_api:<modèle>   # comparison (F35)

Exit code 0 when every executed case passed, 1 otherwise.
"""

import argparse
import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from nfactory_core.config import get_settings
from nfactory_worker.agents import Engines, demo_llm
from nfactory_worker.evals.bench import build_comparison, write_comparison
from nfactory_worker.evals.cases import Case, CaseError, load_cases
from nfactory_worker.evals.checks import score
from nfactory_worker.evals.engines import DEMO, EngineError, EngineSpec, open_engine, parse_engine
from nfactory_worker.evals.report import build_report, load_previous, load_report, write_report
from nfactory_worker.evals.run import CaseRun, EvalEnv, run_case
from nfactory_worker.runner import LocalRunner, Runner, SandboxRunner

ROOT = Path(__file__).resolve().parents[4]
# Local mode has one workspace; its connections are the engines a bench may use.
WORKSPACE = "wks_local"


_GLYPH = {"passed": "✓", "failed": "✗", "skipped": "-"}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # a Windows console defaults to cp1252
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = _parser().parse_args(argv)
    try:
        cases = load_cases(Path(args.datasets))
    except CaseError as exc:
        print(f"Scénarios invalides : {exc}", file=sys.stderr)
        return 2
    if args.only:
        wanted = set(args.only)
        cases = [c for c in cases if c.id in wanted or c.suite in wanted]
    if not cases:
        print("Aucun cas à exécuter.", file=sys.stderr)
        return 2
    try:
        specs = _specs(args.engine or [DEMO])
        engines = asyncio.run(_open_engines(specs))
    except EngineError as exc:
        print(f"Moteur refusé : {exc}", file=sys.stderr)
        return 2
    out = Path(args.out)
    reports: list[dict[str, Any]] = []
    for spec in specs:
        if not spec.demo:
            print(f"{spec.label} : {len(cases)} cas, appels réels facturés par le fournisseur.")
        results = _run_engine(cases, args, engines[spec.label])
        meta = {**_meta(args), "engine": spec.meta()}
        if len(specs) > 1:
            reports.append(build_report(results, meta))
            continue
        previous = load_report(Path(args.compare)) if args.compare else None
        if previous is None and spec.demo:
            previous = load_previous(out)
        report = build_report(results, meta, previous)
        json_path, html_path = write_report(report, out, latest=spec.demo)
        _print_totals(report, f"{json_path} , {html_path}")
        return 1 if report["totals"]["failed"] else 0
    comparison = build_comparison(reports, _meta(args))
    json_path, html_path = write_comparison(comparison, out)
    for report in reports:
        _print_totals(report, report["engine"]["label"])
    print(f"Comparaison : {json_path} , {html_path}")
    return 1 if any(r["totals"]["failed"] for r in reports) else 0


def _specs(texts: list[str]) -> list[EngineSpec]:
    specs = [parse_engine(text) for text in texts]
    labels = [spec.label for spec in specs]
    if len(set(labels)) != len(labels):
        raise EngineError("chaque moteur ne peut être donné qu'une fois.")
    return specs


async def _open_engines(specs: list[EngineSpec]) -> dict[str, Engines]:
    """Demo needs nothing; a real engine is read from the user's connections."""
    opened = {spec.label: Engines.single(demo_llm()) for spec in specs if spec.demo}
    real = [spec for spec in specs if not spec.demo]
    if not real:
        return opened
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            for spec in real:
                opened[spec.label] = await open_engine(spec, session, WORKSPACE, settings)
    finally:
        await engine.dispose()
    return opened


def _run_engine(
    cases: list[Case], args: argparse.Namespace, engines: Engines
) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="nfactory-evals-", dir=args.work) as scratch:
        base = Path(scratch)
        env = EvalEnv(
            base=base,
            runner=_runner(args.runner, base),
            # The supervisor finds a workspace by name on its own volume.
            workspace_root=Path(get_settings().workspace_root)
            if args.runner == "sandbox"
            else None,
            engines=engines,
        )
        return asyncio.run(_run_all(cases, env))


def _meta(args: argparse.Namespace) -> dict[str, Any]:
    return {"version": _version(), "runner": args.runner, "datasets": str(args.datasets)}


def _print_totals(report: dict[str, Any], where: str) -> None:
    totals = report["totals"]
    print(
        f"{totals['passed']} réussis, {totals['failed']} en échec, {totals['skipped']} ignorés "
        f"sur {totals['cases']} cas — {where}"
    )
    for case in report["cases"]:
        if case["status"] == "failed":
            failed = [c for c in case["checks"] if not c["ok"]]
            print(
                f"  ✗ {case['id']} : " + " ; ".join(f"{c['name']} — {c['detail']}" for c in failed)
            )


async def _run_all(cases: list[Case], env: EvalEnv) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for case in cases:
        run: CaseRun = await run_case(case, env)
        checks = score(run)
        metrics = run.metrics() if not run.skipped else {"duration_s": 0.0}
        run.cleanup()
        status = "skipped" if run.skipped else ("passed" if all(c.ok for c in checks) else "failed")
        print(f"  {_GLYPH[status]} {case.id}", flush=True)
        results.append(
            {
                "id": case.id,
                "suite": case.suite,
                "project_type": case.project_type,
                "tags": list(case.tags),
                "status": status,
                "skipped": run.skipped,
                "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in checks],
                "metrics": metrics,
            }
        )
    return results


def _runner(kind: str, base: Path) -> Runner:
    if kind == "sandbox":
        settings = get_settings()
        if not settings.nfactory_sandbox_url:
            raise SystemExit("NFACTORY_SANDBOX_URL absent : lancer scripts/evals.ps1")
        return SandboxRunner(
            settings.nfactory_sandbox_url, settings.nfactory_sandbox_token.get_secret_value()
        )
    return LocalRunner(base / "workspaces", python=sys.executable)


def _version() -> str:
    if os.environ.get("NFACTORY_VERSION"):
        return os.environ["NFACTORY_VERSION"]
    try:
        done = subprocess.run(
            ["git", "describe", "--always", "--dirty"],  # noqa: S607 - git from PATH, fixed arguments
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "inconnue"
    return done.stdout.strip() or "inconnue"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfactory-evals", description="Évals NFactory (spec §14.2)"
    )
    parser.add_argument("--datasets", default=str(ROOT / "evals" / "datasets"))
    parser.add_argument("--out", default=str(ROOT / "evals" / "reports"))
    parser.add_argument("--runner", choices=("local", "sandbox"), default="local")
    parser.add_argument("--only", nargs="*", help="identifiants de cas ou noms de suites")
    parser.add_argument(
        "--compare", default=None, help="rapport JSON à comparer (défaut : latest.json)"
    )
    parser.add_argument("--work", default=None, help="dossier des espaces de travail temporaires")
    parser.add_argument(
        "--engine",
        action="append",
        help="moteur : demo (défaut) ou <fournisseur>:<modèle> connecté dans Moteurs IA ; "
        "plusieurs --engine écrivent une comparaison (bench-*.json/.html)",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
