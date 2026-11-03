"""The eval report (spec §14.2): JSON for machines, a self-contained HTML page for
people. Every figure states its source; a missing measure is null, never a made-up 0."""

import html
import json
import math
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SOURCES = {
    "pass_rate": "cas réussis / cas exécutés (les cas ignorés ne comptent pas)",
    "latency_p50_s": (
        "médiane des durées mesurées par l'horloge de la commande "
        "(run complet, projet de départ compris pour une évolution)"
    ),
    "latency_p95_s": "95e centile (rang le plus proche) des mêmes durées",
    "cost_usd": "somme des coûts des runs ; null si un moteur n'a pas de prix connu",
    "llm_calls": "événements agent.progress des runs",
    "security_findings": "alertes de l'analyse de secrets (événements security.scanned)",
    "adversarial_pass_rate": "cas de la suite adversarial réussis / exécutés",
}


def build_report(
    results: list[dict[str, Any]],
    meta: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ran = [r for r in results if r["status"] != "skipped"]
    passed = [r for r in ran if r["status"] == "passed"]
    by_suite: dict[str, dict[str, int]] = defaultdict(
        lambda: {"passed": 0, "failed": 0, "skipped": 0}
    )
    for r in results:
        by_suite[r["suite"]][r["status"]] += 1
    durations = sorted(r["metrics"]["duration_s"] for r in ran)
    costs = [r["metrics"].get("cost_usd") for r in ran]
    adversarial = [r for r in ran if r["suite"] == "adversarial"]
    figures = {
        "pass_rate": _rate(len(passed), len(ran)),
        "latency_p50_s": _percentile(durations, 50),
        "latency_p95_s": _percentile(durations, 95),
        "cost_usd": None if not costs or None in costs else round(sum(costs), 6),
        "llm_calls": sum(r["metrics"].get("llm_calls", 0) for r in ran),
        "security_findings": sum(r["metrics"].get("findings", 0) for r in ran),
        "adversarial_pass_rate": _rate(
            sum(1 for r in adversarial if r["status"] == "passed"), len(adversarial)
        ),
    }
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        **meta,
        "totals": {
            "cases": len(results),
            "passed": len(passed),
            "failed": len(ran) - len(passed),
            "skipped": len(results) - len(ran),
            "pass_rate": figures["pass_rate"],
        },
        "by_suite": dict(sorted(by_suite.items())),
        "figures": {
            key: {"value": value, "source": SOURCES[key]} for key, value in figures.items()
        },
        "cases": results,
    }
    if previous is not None:
        report["comparison"] = _compare(previous, report)
    return report


def write_report(report: dict[str, Any], out: Path, *, latest: bool = True) -> tuple[Path, Path]:
    """`latest` updates latest.json, the regression baseline (the demo engine's run)."""
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    text = json.dumps(report, ensure_ascii=False, indent=2)
    json_path = out / f"eval-{stamp}.json"
    json_path.write_text(text, encoding="utf-8")
    if latest:
        (out / "latest.json").write_text(text, encoding="utf-8")
    html_path = out / f"eval-{stamp}.html"
    html_path.write_text(render_html(report), encoding="utf-8")
    return json_path, html_path


def load_previous(out: Path) -> dict[str, Any] | None:
    """The last report written in `out`, if any: the baseline of the comparison."""
    return load_report(out / "latest.json")


def load_report(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _compare(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    before = {c["id"]: c["status"] for c in previous.get("cases", [])}
    now = {c["id"]: c["status"] for c in current["cases"]}
    common = sorted(set(before) & set(now))
    return {
        "previous_generated_at": previous.get("generated_at"),
        "previous_version": previous.get("version"),
        "pass_rate_before": previous.get("totals", {}).get("pass_rate"),
        "pass_rate_after": current["totals"]["pass_rate"],
        "regressions": [i for i in common if before[i] == "passed" and now[i] == "failed"],
        "fixed": [i for i in common if before[i] == "failed" and now[i] == "passed"],
        "new_cases": sorted(set(now) - set(before)),
    }


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _percentile(values: list[float], pct: int) -> float | None:
    if not values:
        return None
    rank = max(math.ceil(pct / 100 * len(values)), 1)
    return values[rank - 1]


# --- HTML ---------------------------------------------------------------------------

_STYLE = """
body{font-family:system-ui,sans-serif;margin:2rem auto;max-width:72rem;color:#1d2a44;
  background:#fbf7f0}
h1{font-size:1.6rem}h2{font-size:1.2rem;margin-top:2rem}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{border-bottom:1px solid #e4dccd;padding:.4rem .5rem;text-align:left;vertical-align:top}
.ok{color:#2f6b4f}.ko{color:#a3362a}.skip{color:#6b6b6b}
.note{background:#fff3c4;padding:.6rem .8rem;border-left:4px solid #d9a400}
code{font-family:ui-monospace,monospace;font-size:.85em}small{color:#5b6475}
"""

# A status always shows a glyph and a French label, never color alone.
_STATUS = {
    "passed": ("✓", "Réussi", "ok"),
    "failed": ("✗", "Échec", "ko"),
    "skipped": ("-", "Ignoré", "skip"),
}
_DEMO_NOTE = (
    "<p class='note'>Moteur démo (déterministe) : ces chiffres mesurent le pipeline, "
    "les recettes, les vérifications et les garde-fous, pas la qualité d'un modèle.</p>"
)


def render_html(report: dict[str, Any]) -> str:
    e = html.escape
    engine = report.get("engine", {})
    totals = report["totals"]
    header = (
        f"<p><small>{e(report['generated_at'])} · version {e(str(report.get('version')))}"
        f" · moteur {e(str(engine.get('provider')))} / {e(str(engine.get('model')))}"
        f" · runner {e(str(report.get('runner')))}</small></p>"
    )
    summary = (
        f"<p>{totals['passed']} réussis, {totals['failed']} en échec, "
        f"{totals['skipped']} ignorés sur {totals['cases']} cas.</p>"
    )
    parts = [
        "<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'>",
        f"<title>Évals NFactory — {e(report['generated_at'])}</title>",
        f"<style>{_STYLE}</style></head><body><h1>Évals NFactory</h1>",
        header,
        _DEMO_NOTE if engine.get("demo") else "",
        summary,
        "<h2>Chiffres et sources</h2>",
        _table(
            ("Mesure", "Valeur", "Source"),
            [_figure_row(k, f) for k, f in report["figures"].items()],
        ),
        _comparison(report.get("comparison")),
        "<h2>Cas</h2>",
        _table(("Cas", "État", "Durée", "Vérifications"), [_case_row(c) for c in report["cases"]]),
        "</body></html>",
    ]
    return "".join(parts)


def _table(headers: tuple[str, ...], rows: list[str]) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    return f"<table><tr>{head}</tr>{''.join(rows)}</table>"


def _figure_row(key: str, figure: dict[str, Any]) -> str:
    e = html.escape
    return (
        f"<tr><td><code>{e(key)}</code></td><td>{e(_show(figure['value']))}</td>"
        f"<td><small>{e(figure['source'])}</small></td></tr>"
    )


def _case_row(case: dict[str, Any]) -> str:
    e = html.escape
    glyph, label, css = _STATUS[case["status"]]
    if case.get("skipped"):
        detail = e(case["skipped"])
    else:
        detail = "<br>".join(
            f"{'✓' if c['ok'] else '✗'} <code>{e(c['name'])}</code> {e(c['detail'])}"
            for c in case["checks"]
        )
    where = f"{e(case['suite'])} · {e(case['project_type'])}"
    duration = e(_show(case["metrics"].get("duration_s")))
    return (
        f"<tr><td><code>{e(case['id'])}</code><br><small>{where}</small></td>"
        f"<td class='{css}'>{glyph} {label}</td><td>{duration} s</td><td>{detail}</td></tr>"
    )


def _comparison(comparison: dict[str, Any] | None) -> str:
    if not comparison:
        return ""
    e = html.escape
    before = _show(comparison["pass_rate_before"])
    after = _show(comparison["pass_rate_after"])
    items = [
        f"Taux de réussite : {e(before)} → {e(after)}",
        f"Régressions : {e(', '.join(comparison['regressions']) or 'aucune')}",
        f"Corrigés : {e(', '.join(comparison['fixed']) or 'aucun')}",
        f"Nouveaux cas : {e(', '.join(comparison['new_cases']) or 'aucun')}",
    ]
    lis = "".join(f"<li>{item}</li>" for item in items)
    return f"<h2>Comparaison avec le rapport précédent</h2><ul>{lis}</ul>"


def _show(value: Any) -> str:
    if value is None:
        return "non mesuré"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)
