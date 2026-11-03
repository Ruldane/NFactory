"""Baseline load test of a running stack (task 5.6). It measures; it promises nothing.

    uv run python scripts/load_test.py                       # after ./scripts/dev.ps1
    uv run python scripts/load_test.py --levels 1,10,50 --duration 20 --runs 10

Two phases:
- reads: N concurrent clients call the dashboard's read endpoints for a fixed time;
- runs: launches demo runs at once and times each one until it ends.

Runs are launched only on the demo engine: the script refuses when demo mode is off or
an engine is routed, so a load test never bills a provider. The report (JSON, plus a
Markdown summary) lands in loadtests/reports/ with the machine, the parameters and the
source of every figure. A figure that was not measured is null ("Non mesuré").
"""

import argparse
import asyncio
import json
import math
import os
import platform
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
API = "http://127.0.0.1:8000/api/v1"
TERMINAL = {"COMPLETED", "PARTIAL", "FAILED", "CANCELLED"}
READS = ("/dashboard/summary", "/projects?limit=20", "/saved-recipes", "/approvals")
REQUEST = "Un classeur Excel de suivi des dépenses, avec catégorie, montant et date."

SOURCES = {
    "latency": "durée de chaque requête HTTP mesurée côté client (time.perf_counter), "
    "percentiles au rang le plus proche",
    "throughput_rps": "requêtes terminées / durée de la phase (horloge du client)",
    "error_rate": "réponses non 2xx ou sans réponse / requêtes",
    "run_duration": "du POST de lancement à l'état terminal lu sur GET /runs/{id} "
    "(sondage toutes les 0,5 s : précision ±0,5 s)",
    "runs_per_minute": "runs terminés par minute de phase (horloge du client)",
}

Sample = tuple[float, int | None]  # seconds, HTTP status (None: no answer)


def percentile(values: list[float], pct: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def _ms(value: float | None) -> float | None:
    return None if value is None else round(value * 1000, 1)


def summarize(samples: list[Sample], wall_s: float) -> dict[str, Any]:
    latencies = [s for s, _ in samples]
    errors = sum(1 for _, status in samples if status is None or not 200 <= status < 300)
    return {
        "requests": len(samples),
        "errors": errors,
        "error_rate": round(errors / len(samples), 4) if samples else None,
        "throughput_rps": round(len(samples) / wall_s, 1) if wall_s > 0 else None,
        "p50_ms": _ms(percentile(latencies, 50)),
        "p95_ms": _ms(percentile(latencies, 95)),
        "p99_ms": _ms(percentile(latencies, 99)),
        "max_ms": _ms(max(latencies)) if latencies else None,
    }


def require_demo_engine(settings: dict[str, Any], routing: dict[str, Any]) -> None:
    """Stop unless new runs go to the demo engine (no provider is ever billed)."""
    config = routing.get("routing") or {}
    routed = config.get("default") is not None or bool(config.get("roles"))
    if not settings.get("demo_mode") or routed:
        raise SystemExit(
            "Le test de charge lance des runs : il exige le moteur démo (mode démo actif, "
            "aucun moteur routé dans Moteurs IA). Rien n'a été lancé."
        )


async def _read_phase(
    client: httpx.AsyncClient, concurrency: int, duration: float
) -> dict[str, Any]:
    samples: list[Sample] = []
    deadline = time.perf_counter() + duration

    async def worker(offset: int) -> None:
        i = offset
        while time.perf_counter() < deadline:
            path = READS[i % len(READS)]
            i += 1
            start = time.perf_counter()
            try:
                status: int | None = (await client.get(path)).status_code
            except httpx.HTTPError:
                status = None
            samples.append((time.perf_counter() - start, status))

    started = time.perf_counter()
    await asyncio.gather(*(worker(n) for n in range(concurrency)))
    return {"concurrency": concurrency, **summarize(samples, time.perf_counter() - started)}


async def _one_run(client: httpx.AsyncClient, project_id: str, limit_s: float) -> tuple[float, str]:
    start = time.perf_counter()
    launched = await client.post(
        f"/projects/{project_id}/runs",
        json={"request": REQUEST},
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    if launched.status_code not in (200, 201):
        return time.perf_counter() - start, f"refusé ({launched.status_code})"
    run_id = launched.json()["id"]
    while time.perf_counter() - start < limit_s:
        state = (await client.get(f"/runs/{run_id}")).json()["state"]
        if state in TERMINAL:
            return time.perf_counter() - start, state
        await asyncio.sleep(0.5)
    return time.perf_counter() - start, "délai dépassé"


async def _run_phase(client: httpx.AsyncClient, runs: int, limit_s: float) -> dict[str, Any]:
    project = await client.post("/projects", json={"title": "Test de charge", "type": "excel"})
    project.raise_for_status()
    started = time.perf_counter()
    done = await asyncio.gather(
        *(_one_run(client, project.json()["id"], limit_s) for _ in range(runs))
    )
    wall = time.perf_counter() - started
    durations = [d for d, state in done if state == "COMPLETED"]
    states: dict[str, int] = {}
    for _, state in done:
        states[state] = states.get(state, 0) + 1
    return {
        "runs": runs,
        "project_id": project.json()["id"],
        "states": states,
        "wall_s": round(wall, 1),
        "runs_per_minute": round(len(durations) / wall * 60, 1) if durations and wall else None,
        "p50_s": _round(percentile(durations, 50)),
        "p95_s": _round(percentile(durations, 95)),
        "max_s": _round(max(durations)) if durations else None,
    }


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def _show(value: Any) -> str:
    return "Non mesuré" if value is None else str(value)


def render_markdown(report: dict[str, Any]) -> str:
    machine, params = report["machine"], report["parameters"]
    lines = [
        "# Test de charge de base",
        "",
        f"Généré le {report['generated_at']} · version {report['version']} · "
        f"{machine['os']}, {machine['cpus']} processeurs, Python {machine['python']}.",
        f"Phase de lecture : {params['duration_s']} s par niveau ; runs lancés : {params['runs']}.",
        "Mesures d'un seul poste, toute la pile en local : ce n'est pas une capacité garantie.",
        "",
        "## Lectures (API du dashboard)",
        "",
        "| Clients simultanés | Requêtes | Erreurs | Débit (req/s) "
        "| p50 (ms) | p95 (ms) | p99 (ms) | max (ms) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for phase in report["read_phases"]:
        cells = [phase[k] for k in ("concurrency", "requests", "errors", "throughput_rps")]
        cells += [phase[k] for k in ("p50_ms", "p95_ms", "p99_ms", "max_ms")]
        lines.append("| " + " | ".join(_show(c) for c in cells) + " |")
    lines += ["", "## Runs simultanés (moteur démo)", ""]
    run = report["run_phase"]
    if run is None:
        lines.append("Non mesuré (aucun run demandé).")
    else:
        lines += [
            f"- Runs lancés : {run['runs']} ; états finaux : {run['states']}",
            f"- Durée de la phase : {_show(run['wall_s'])} s ; runs livrés par minute : "
            f"{_show(run['runs_per_minute'])}",
            f"- Durée d'un run livré : p50 {_show(run['p50_s'])} s, p95 {_show(run['p95_s'])} s, "
            f"max {_show(run['max_s'])} s",
        ]
    lines += ["", "## Sources", ""]
    lines += [f"- **{key}** : {text}" for key, text in report["sources"].items()]
    return "\n".join(lines) + "\n"


def _version() -> str:
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


async def _measure(args: argparse.Namespace) -> dict[str, Any]:
    limits = httpx.Limits(max_connections=max(args.levels) + args.runs)
    async with httpx.AsyncClient(base_url=args.api, timeout=30, limits=limits) as client:
        settings = (await client.get("/settings")).json()
        routing = (await client.get("/routing")).json()
        if args.runs:
            require_demo_engine(settings, routing)
        reads = [await _read_phase(client, level, args.duration) for level in args.levels]
        run = await _run_phase(client, args.runs, args.run_timeout) if args.runs else None
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "version": _version(),
        "machine": {
            "os": f"{platform.system()} {platform.release()}",
            "cpus": os.cpu_count(),
            "python": platform.python_version(),
        },
        "stack": {"api": args.api, "demo_mode": settings.get("demo_mode")},
        "parameters": {
            "levels": args.levels,
            "duration_s": args.duration,
            "runs": args.runs,
            "endpoints": list(READS),
        },
        "read_phases": reads,
        "run_phase": run,
        "sources": SOURCES,
    }


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Test de charge de base (tâche 5.6)")
    parser.add_argument("--api", default=API)
    parser.add_argument(
        "--levels", default="1,10,50", help="clients simultanés, séparés par des virgules"
    )
    parser.add_argument("--duration", type=float, default=15.0, help="secondes par niveau")
    parser.add_argument(
        "--runs", type=int, default=10, help="runs démo lancés en même temps (0 : aucun)"
    )
    parser.add_argument("--run-timeout", type=float, default=600.0)
    parser.add_argument("--out", default=str(ROOT / "loadtests" / "reports"))
    args = parser.parse_args(argv)
    args.levels = [int(v) for v in str(args.levels).split(",") if v.strip()]
    report = asyncio.run(_measure(args))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (out / f"load-{stamp}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = render_markdown(report)
    (out / f"load-{stamp}.md").write_text(summary, encoding="utf-8")
    print(summary)
    print(f"Rapport : {out / f'load-{stamp}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
