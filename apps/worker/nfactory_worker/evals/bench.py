"""Provider comparison (task 5.5, spec F35): the eval reports of several engines on the
same cases, side by side. Every figure comes from a report and states its source; a
missing measure stays null ("Non mesuré"), never a made-up 0.

Interface: build_comparison, write_comparison, render_comparison_html.
"""

import html
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nfactory_worker.evals.report import SOURCES

FIGURES = ("pass_rate", "latency_p50_s", "latency_p95_s", "cost_usd", "llm_calls")
BENCH_SOURCES = {
    **{key: SOURCES[key] for key in FIGURES},
    "security_findings": SOURCES["security_findings"],
    "input_tokens": "somme des jetons d'entrée annoncés par le fournisseur (agent.progress) ; "
    "null si un appel n'en annonce pas",
    "output_tokens": "somme des jetons de sortie annoncés par le fournisseur ; même règle",
    "matrix": "résultat de chaque cas pour chaque moteur ; null si le cas n'a pas tourné",
}
_LABELS = {
    "pass_rate": "Taux de réussite",
    "latency_p50_s": "Latence p50 (s)",
    "latency_p95_s": "Latence p95 (s)",
    "cost_usd": "Coût ($)",
    "llm_calls": "Appels IA",
    "security_findings": "Alertes sécurité",
    "input_tokens": "Jetons d'entrée",
    "output_tokens": "Jetons de sortie",
}
_STATUS = {"passed": "✓ réussi", "failed": "✗ échec", "skipped": "- ignoré", None: "Non exécuté"}


def build_comparison(reports: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    engines = []
    for report in reports:
        figures = report["figures"]
        ran = [c for c in report["cases"] if c["status"] != "skipped"]
        engines.append(
            {
                "engine": report["engine"]["label"],
                "provider": report["engine"]["provider"],
                "model": report["engine"]["model"],
                "demo": report["engine"]["demo"],
                **{key: figures[key]["value"] for key in FIGURES},
                "security_findings": figures["security_findings"]["value"],
                "input_tokens": _sum(ran, "input_tokens"),
                "output_tokens": _sum(ran, "output_tokens"),
            }
        )
    case_ids: list[str] = []
    for report in reports:
        case_ids += [c["id"] for c in report["cases"] if c["id"] not in case_ids]
    status = {(r["engine"]["label"], c["id"]): c["status"] for r in reports for c in r["cases"]}
    matrix = [
        {"case": cid, "results": {e["engine"]: status.get((e["engine"], cid)) for e in engines}}
        for cid in case_ids
    ]
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        **meta,
        "engines": engines,
        "matrix": matrix,
        "sources": BENCH_SOURCES,
        "reports": reports,
    }


def write_comparison(comparison: dict[str, Any], out: Path) -> tuple[Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path, html_path = out / f"bench-{stamp}.json", out / f"bench-{stamp}.html"
    json_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_comparison_html(comparison), encoding="utf-8")
    return json_path, html_path


def _sum(cases: list[dict[str, Any]], key: str) -> int | None:
    values = [c["metrics"].get(key) for c in cases]
    if not values or any(v is None for v in values):
        return None
    return sum(int(v) for v in values)


def _show(value: Any, key: str = "") -> str:
    if value is None:
        return "Non mesuré"
    if key == "pass_rate":
        return f"{value * 100:.0f} %"
    if isinstance(value, float):
        return f"{value:.4f}" if key == "cost_usd" else f"{value:.2f}"
    return str(value)


def render_comparison_html(comparison: dict[str, Any]) -> str:
    esc = html.escape
    engines = comparison["engines"]
    keys = (*FIGURES, "security_findings", "input_tokens", "output_tokens")
    head = "".join(
        f"<th>{esc(e['engine'])}{' <small>(moteur démo)</small>' if e['demo'] else ''}</th>"
        for e in engines
    )
    figure_rows = "".join(
        f"<tr><th scope='row'>{esc(_LABELS[k])}<br><small>{esc(BENCH_SOURCES[k])}</small></th>"
        + "".join(f"<td>{esc(_show(e[k], k))}</td>" for e in engines)
        + "</tr>"
        for k in keys
    )
    case_rows = "".join(
        f"<tr><th scope='row'>{esc(row['case'])}</th>"
        + "".join(f"<td>{esc(_STATUS[row['results'][e['engine']]])}</td>" for e in engines)
        + "</tr>"
        for row in comparison["matrix"]
    )
    demo_note = (
        "<p>Le moteur démo est déterministe et gratuit : il mesure le pipeline, pas un modèle.</p>"
        if any(e["demo"] for e in engines)
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>Comparaison des moteurs · NFactory</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;color:#1d2a44;background:#f6efe4}}
table{{border-collapse:collapse;margin:1rem 0}}th,td{{border:1px solid #c9c2b5;padding:.4rem .7rem;
text-align:left;vertical-align:top}}small{{color:#5b6275;font-weight:normal}}
</style></head><body>
<h1>Comparaison des moteurs</h1>
<p>Version {esc(str(comparison.get("version", "inconnue")))} · générée le
{esc(comparison["generated_at"])} · mêmes cas pour chaque moteur.</p>
{demo_note}
<h2>Chiffres</h2>
<table><thead><tr><th>Mesure</th>{head}</tr></thead><tbody>{figure_rows}</tbody></table>
<h2>Cas par moteur</h2>
<table><thead><tr><th>Cas</th>{head}</tr></thead><tbody>{case_rows}</tbody></table>
</body></html>
"""
