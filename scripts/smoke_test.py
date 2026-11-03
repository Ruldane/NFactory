"""End-to-end smoke test against a running stack. Standard library only.

Usage: python scripts/smoke_test.py   (after `docker compose up`)
Waits for the services, then checks the API directly and through the dashboard proxy.
"""

import io
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

API = "http://127.0.0.1:8000/api/v1"
DASHBOARD = "http://127.0.0.1:3000"


def get(url: str) -> tuple[int, Any]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 - local URLs only
            raw = response.read().decode()
            status = response.status
    except urllib.error.HTTPError as exc:
        raw, status = exc.read().decode(), exc.code
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, raw


def post(url: str, body: dict[str, Any]) -> tuple[int, Any]:
    request = urllib.request.Request(  # noqa: S310 - local URLs only
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - local
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode() or "{}")


def upload(url: str, filename: str, data: bytes) -> tuple[int, Any]:
    """multipart/form-data with one file field, standard library only."""
    boundary = "nfactory-smoke-boundary"
    head = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{filename}"\r\nContent-Type: text/markdown\r\n\r\n'
    )
    body = head.encode() + data + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(  # noqa: S310 - local URLs only
        url,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - local
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode() or "{}")


SMOKE_DOC = (
    b"# Rapport des heures\n\nLe rapport hebdomadaire des heures regroupe les equipes "
    b"et totalise les heures par semaine.\n"
)

# Phase 3 validation (spec §3.1, scenario A): the "IT licence manager" demo.
LICENCE_DOC = (
    b"# Politique de gestion des licences\n\n"
    b"Chaque licence logicielle est suivie avec son editeur, son nombre de postes et sa date "
    b"d'expiration. Les licences qui expirent dans moins de 30 jours declenchent une alerte.\n"
)
LICENCE_REQUEST = (
    "Crée une application interne de suivi des licences : dashboard React, API Python, "
    "PostgreSQL, export Excel, alertes d'expiration. Génère les tests et la documentation."
)


def run_to_the_end(project_type: str, request: str, timeout_s: float = 240) -> dict[str, Any]:
    """Create a project, launch a run, wait until the worker finishes it."""
    _, project = post(f"{API}/projects", {"title": "Smoke test", "type": project_type})
    _, run = post(f"{API}/projects/{project['id']}/runs", {"request": request})
    return wait_until_finished(run["id"], timeout_s)


def wait_until_finished(run_id: str, timeout_s: float) -> dict[str, Any]:
    run = {"id": run_id}
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        _, current = get(f"{API}/runs/{run['id']}")
        if current["state"] in {"COMPLETED", "FAILED", "CANCELLED"}:
            return dict(current)
        time.sleep(2)
    return {"id": run["id"], "state": "TIMEOUT", "error": f"pas fini après {timeout_s:.0f} s"}


def wait_for(url: str, timeout_s: float = 90) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if get(url)[0] == 200:
                return
        except OSError:
            pass
        time.sleep(2)
    raise SystemExit(f"✕ {url} ne répond pas après {timeout_s:.0f} s")


def check_licence_demo(run: dict[str, Any], expect: Any) -> None:
    """Phase 3 validation: preview React + API, Excel export, tests, cited sources, repairs."""
    steps = {s["name"]: s for s in run["steps"]}
    requirements = steps["requirements"]["output"]
    cited = [c["path"] for c in requirements.get("sources", [])]
    expect("Démo licences : politique citée", "politique-licences.md" in cited, str(cited))
    plural = requirements["brief"]["entity"]["plural"]
    check_preview(run["id"], expect, plural)
    # Any repair the debug loop applied is traced; none is also a valid outcome.
    repairs = [r for s in run["steps"] for r in (s["output"] or {}).get("repairs", [])]
    expect(
        f"Réparations tracées ({len(repairs)})",
        all(r.get("step") and "attempt" in r for r in repairs),
        str(repairs)[:200],
    )


def check_change_request(parent: dict[str, Any], expect: Any) -> None:
    """Task 3.11 (scenario E): a change on the delivered app, retested, with its diff."""
    body = {"request": "Ajoute le champ responsable", "parent_run_id": parent["id"]}
    status, child = post(f"{API}/projects/{parent['project']['id']}/runs", body)
    expect("Évolution lancée", status == 201, str(child)[:200])
    if status != 201:
        return
    run = wait_until_finished(child["id"], 420)
    expect("Évolution terminée", run["state"] == "COMPLETED", str(run.get("error"))[:300])
    if run["state"] != "COMPLETED":
        return
    steps = {s["name"]: s for s in run["steps"]}
    report = steps["tests"]["output"].get("report", {})
    expect("Évolution retestée", report.get("passed", 0) > 0 and report.get("failed") == 0)
    changes = steps["package"]["output"].get("changes", {})
    expect("Diff de l'évolution", bool(changes.get("modified")), str(changes)[:200])


def fetch_bytes(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - local URLs
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def check_excel_export(base_url: str, plural: str, expect: Any) -> None:
    """The generated app's Excel export, downloaded through the preview gateway."""
    from openpyxl import load_workbook

    status, data = fetch_bytes(f"{base_url}api/{plural}/export.xlsx")
    ok = status == 200 and data.startswith(b"PK")
    header: tuple[Any, ...] = ()
    if ok:
        sheet = load_workbook(io.BytesIO(data)).worksheets[0]
        header = next(sheet.iter_rows(max_row=1, values_only=True))
    expect("Export Excel de l'application", ok and header[:1] == ("N°",), str(header)[:200])


def check_preview(run_id: str, expect: Any, plural: str = "") -> None:
    """Task 3.10: the generated app runs in the sandbox, behind the preview gateway."""
    status, started = post(f"{API}/runs/{run_id}/preview", {})
    expect("Aperçu démarré", status == 200, str(started)[:200])
    if status != 200:
        return
    deadline = time.monotonic() + 60
    page: Any = ""
    while time.monotonic() < deadline:
        code, page = get(started["url"])
        if code == 200 and 'id="root"' in str(page):
            break
        time.sleep(1)
    expect("Aperçu servi par la passerelle", 'id="root"' in str(page), str(page)[:200])
    if plural:
        check_excel_export(started["url"], plural, expect)
    request = urllib.request.Request(f"{API}/runs/{run_id}/preview", method="DELETE")  # noqa: S310
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - local URL
        expect("Aperçu arrêté", response.status == 204)


def main() -> int:
    wait_for(f"{API}/health")
    wait_for(f"{DASHBOARD}/")
    failures: list[str] = []

    def expect(label: str, ok: bool, detail: str = "") -> None:
        print(f"{'✓' if ok else '✕'} {label}{f' — {detail}' if detail and not ok else ''}")
        if not ok:
            failures.append(label)

    status, ready = get(f"{API}/ready")
    expect("API prête (base, pgvector, Redis)", status == 200, str(ready))

    status, summary = get(f"{DASHBOARD}/api/v1/dashboard/summary")
    expect("Résumé via le proxy du dashboard", status == 200, str(summary)[:200])
    if status == 200:
        expect("Indicateurs cohérents", summary["runs"]["total"] >= 0)

    status, projects = get(f"{API}/projects?limit=1")
    expect("Liste des projets", status == 200 and "items" in projects, str(projects)[:200])

    status, _ = get(f"{DASHBOARD}/projects")
    expect("Page Projets du dashboard", status == 200)

    status, missing = get(f"{API}/projects/proj_does_not_exist")
    expect("Erreur structurée sur projet inconnu", status == 404 and "error" in missing)

    # Provider hub (phase 2): listed honestly, never "connected" without a test.
    status, providers = get(f"{API}/providers")
    kinds = {p["kind"]: p for p in providers.get("providers", [])} if status == 200 else {}
    expect("Fournisseurs listés", {"openai_api", "anthropic_api", "ollama_local"} <= set(kinds))
    expect(
        "Agents de code locaux en phase 4",
        not kinds.get("codex_local", {}).get("available", True),
    )
    status, routing = get(f"{API}/routing")
    expect("Routage des rôles", status == 200 and "routing" in routing, str(routing)[:200])
    status, _ = get(f"{DASHBOARD}/providers")
    expect("Page Moteurs IA du dashboard", status == 200)

    # Knowledge base (phase 3): upload, hybrid search with a citation, its page.
    status, doc = upload(f"{API}/knowledge/documents", "smoke-heures.md", SMOKE_DOC)
    expect("Import d'un document", status in (200, 201), str(doc)[:200])
    status, found = get(f"{API}/knowledge/search?q=rapport%20des%20heures")
    hits = found.get("hits", []) if status == 200 else []
    expect(
        "Recherche avec citation",
        any(h["path"] == "smoke-heures.md" and h["start_line"] >= 1 for h in hits),
        str(found)[:200],
    )
    status, _ = get(f"{DASHBOARD}/knowledge")
    expect("Page Base de connaissances", status == 200)
    status, doc = upload(f"{API}/knowledge/documents", "politique-licences.md", LICENCE_DOC)
    expect("Import de la politique des licences", status in (200, 201), str(doc)[:200])

    # A real run: worker, LangGraph pipeline, sandbox checks, stored deliverable.
    status, recipes = get(f"{API}/recipes")
    expect("Catalogue des recettes", status == 200 and bool(recipes.get("items")))
    run = run_to_the_end("excel", "Rapport hebdomadaire des heures par équipe")
    expect("Run Excel terminé par le worker", run["state"] == "COMPLETED", str(run.get("error")))
    if run["state"] == "COMPLETED":
        _, artifacts = get(f"{API}/runs/{run['id']}/artifacts")
        names = [a["filename"] for a in artifacts["items"]]
        expect("Livrable .xlsx et ZIP stockés", any(n.endswith(".xlsx") for n in names), str(names))
        status, _ = get(f"{DASHBOARD}/runs/{run['id']}")
        expect("Page du run dans le dashboard", status == 200)
        requirements = next(s for s in run["steps"] if s["name"] == "requirements")
        cited = [c["path"] for c in requirements["output"].get("sources", [])]
        expect("Le run cite la base de connaissances", "smoke-heures.md" in cited, str(cited))

    # Phase 3 recipes: their tools (pwsh, node) exist only in the sandbox image.
    for project_type, request, label in (
        ("powershell", "Contrôle de l'inventaire des logiciels installés", "PowerShell (Pester)"),
        ("webapp", LICENCE_REQUEST, "web (pytest + Vitest)"),
    ):
        run = run_to_the_end(project_type, request, timeout_s=420)
        expect(f"Run {label} terminé", run["state"] == "COMPLETED", str(run.get("error"))[:300])
        if run["state"] == "COMPLETED":
            tests = next(s for s in run["steps"] if s["name"] == "tests")
            report = tests["output"].get("report", {})
            expect(f"Tests {label} exécutés", report.get("passed", 0) > 0, str(report)[:200])
            if project_type == "webapp":
                check_licence_demo(run, expect)
                check_change_request(run, expect)

    print("Smoke test réussi." if not failures else f"{len(failures)} vérification(s) en échec.")
    return 1 if failures else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
