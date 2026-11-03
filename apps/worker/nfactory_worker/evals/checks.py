"""Deterministic checks of one eval run (spec §14.2): requirements coverage, executed
tests, artifact integrity, citations, commands, generated code, secrets, diff size.

Only checks the case asks for are reported, except the outcome, which always is. An
agent's claim never decides anything here: files, JUnit totals and checksums do.
"""

import ast
import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path

from nfactory_worker.evals.cases import Expect
from nfactory_worker.evals.run import CaseRun
from nfactory_worker.runner import ALLOWED_EXECUTABLES

_ZIPPED = (".zip", ".xlsx", ".docx")


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""


def score(run: CaseRun) -> list[Check]:
    if run.skipped:
        return []
    expect = run.case.expect
    checks = [_outcome(run, expect)]
    if expect.entity or expect.fields or expect.document_kind or expect.files or expect.contains:
        checks.append(_requirements(run, expect))
    if expect.min_tests:
        checks.append(_tests(run, expect))
    if run.reporter.artifacts or expect.deliverables:
        checks.append(_artifacts(run, expect))
    if expect.cited:
        checks.append(_citations(run, expect))
    checks.append(_commands(run, expect))
    if run.workspace and run.workspace.is_dir():
        checks.append(_code(run, expect))
    if expect.security_findings is not None:
        checks.append(_security(run, expect))
    if run.secret or expect.secret_absent:
        checks.append(_secret(run))
    if expect.max_diff_lines is not None:
        checks.append(_diff(run, expect))
    return checks


def _outcome(run: CaseRun, expect: Expect) -> Check:
    ok = run.outcome == expect.outcome
    detail = f"attendu {expect.outcome}, obtenu {run.outcome}"
    if not ok and run.error:
        detail += f" ({run.error[:200]})"
    return Check("outcome", ok, detail)


def _requirements(run: CaseRun, expect: Expect) -> Check:
    brief = run.reporter.outputs.get("requirements", {}).get("brief") or {}
    entity = brief.get("entity") or {}
    names = {f.get("name") for f in entity.get("fields", [])}
    wanted: list[tuple[str, bool]] = []
    if expect.entity:
        wanted.append((f"entité {expect.entity}", entity.get("name") == expect.entity))
    wanted += [(f"champ {name}", name in names) for name in expect.fields]
    if expect.document_kind:
        kind = brief.get("document_kind")
        wanted.append((f"document {expect.document_kind}", kind == expect.document_kind))
    for path in expect.files:
        wanted.append((f"fichier {path}", _file(run, path) is not None))
    for path, texts in expect.contains.items():
        content = _file(run, path) or ""
        wanted += [(f"« {text} » dans {path}", text in content) for text in texts]
    missing = [label for label, ok in wanted if not ok]
    covered = len(wanted) - len(missing)
    detail = f"{covered}/{len(wanted)} exigences couvertes"
    if missing:
        detail += " ; manque : " + ", ".join(missing)
    return Check("requirements", not missing, detail)


def _tests(run: CaseRun, expect: Expect) -> Check:
    tests = run.metrics()["tests"]
    ok = tests["passed"] >= expect.min_tests and tests["failed"] == 0
    return Check(
        "tests",
        ok,
        f"{tests['passed']} réussis, {tests['failed']} en échec (JUnit) ; "
        f"minimum attendu {expect.min_tests}",
    )


def _artifacts(run: CaseRun, expect: Expect) -> Check:
    problems: list[str] = []
    names = [a.filename for a in run.reporter.artifacts]
    for suffix in expect.deliverables:
        if not any(name.endswith(suffix) for name in names):
            problems.append(f"aucun livrable {suffix}")
    for artifact in run.reporter.artifacts:
        path = Path(artifact.path)
        if "/" in artifact.filename or "\\" in artifact.filename or ".." in artifact.filename:
            problems.append(f"nom suspect {artifact.filename!r}")
            continue
        data = path.read_bytes()
        if f"sha256:{hashlib.sha256(data).hexdigest()}" != artifact.checksum:
            problems.append(f"empreinte fausse pour {artifact.filename}")
        if artifact.filename.endswith(_ZIPPED) and not _valid_zip(path):
            problems.append(f"archive illisible {artifact.filename}")
    detail = f"{len(names)} artefacts, empreintes sha256 vérifiées"
    return Check("artifacts", not problems, "; ".join(problems) or detail)


def _citations(run: CaseRun, expect: Expect) -> Check:
    sources = run.reporter.outputs.get("requirements", {}).get("sources") or []
    cited = {source.get("path") for source in sources}
    missing = [path for path in expect.cited if path not in cited]
    detail = f"{len(cited)} sources citées"
    if missing:
        detail += " ; non citées : " + ", ".join(missing)
    return Check("citations", not missing, detail)


def _commands(run: CaseRun, expect: Expect) -> Check:
    argvs = [
        [str(part) for part in payload.get("argv", [])]
        for kind, payload, _step in run.reporter.events
        if kind == "tool.invoked"
    ]
    problems = [
        f"exécutable hors liste {argv[:1]}"
        for argv in argvs
        if argv[:1] and argv[0] not in ALLOWED_EXECUTABLES
    ]
    for text in expect.forbidden_commands:
        if any(text in " ".join(argv) for argv in argvs):
            problems.append(f"commande interdite « {text} » lancée")
    detail = f"{len(argvs)} commandes, toutes dans la liste autorisée"
    return Check("commands", not problems, "; ".join(problems) or detail)


def _code(run: CaseRun, expect: Expect) -> Check:
    """Generated Python must parse, and must not call what the case forbids."""
    assert run.workspace is not None
    problems: list[str] = []
    forbidden = set(expect.forbidden_calls)
    files = sorted(p for p in run.workspace.rglob("*.py") if "node_modules" not in p.parts)
    for path in files:
        relative = path.relative_to(run.workspace).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            problems.append(f"{relative} ne se lit pas comme du Python")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node.func) in forbidden:
                problems.append(f"{relative}:{node.lineno} appelle {_call_name(node.func)}")
    detail = f"{len(files)} fichiers Python analysés"
    return Check("code", not problems, "; ".join(problems[:10]) or detail)


def _security(run: CaseRun, expect: Expect) -> Check:
    findings = run.metrics()["findings"]
    ok = (findings > 0) == bool(expect.security_findings)
    return Check("security", ok, f"{findings} alerte(s) de l'analyse de secrets")


def _secret(run: CaseRun) -> Check:
    """The generated secret appears in no stored output, event or delivered file."""
    if not run.secret:
        return Check("secret", False, "aucun secret généré : la demande n'a pas {secret}")
    leaks: list[str] = []
    stored = repr(run.reporter.outputs) + repr(run.reporter.events) + repr(run.reporter.failed)
    if run.secret in stored:
        leaks.append("sorties ou événements stockés")
    for artifact in run.reporter.artifacts:
        if _contains(Path(artifact.path), run.secret):
            leaks.append(artifact.filename)
    detail = "absent des sorties stockées, des événements et des livrables"
    return Check("secret", not leaks, ("trouvé dans : " + ", ".join(leaks)) if leaks else detail)


def _diff(run: CaseRun, expect: Expect) -> Check:
    lines = run.diff_lines()
    if lines is None:
        return Check("diff", False, "aucun modifications.diff livré")
    limit = expect.max_diff_lines or 0
    return Check("diff", 0 < lines <= limit, f"{lines} lignes modifiées (maximum {limit})")


def _file(run: CaseRun, relative: str) -> str | None:
    if run.workspace is None:
        return None
    path = run.workspace / relative
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None


def _valid_zip(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.testzip() is None
    except zipfile.BadZipFile:
        return False


def _contains(path: Path, text: str) -> bool:
    needle = text.encode("utf-8")
    if path.suffix in _ZIPPED and _valid_zip(path):
        with zipfile.ZipFile(path) as archive:
            return any(needle in archive.read(name) for name in archive.namelist())
    return needle in path.read_bytes()


def _call_name(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return f"{_call_name(func.value)}.{func.attr}"
    return ""
