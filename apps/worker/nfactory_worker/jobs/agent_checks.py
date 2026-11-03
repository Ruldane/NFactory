"""Test an agent's change in NFactory's sandbox (task 4.4, spec §6.5).

A coding agent (the user's Codex, or the user's own Claude Code on a handoff) changed a
worktree on the user's machine. The bridge only hands over the files; this job copies them
into a throwaway workspace and runs the tests through the runner, so generated code runs
in the sandbox (no network, read-only) and never on the bridge. The verdict comes from the
JUnit report, never from what the agent said.

Only pytest projects are tested for now; anything else is `not_tested`, said plainly. The
repository's own dependencies are not installed (the sandbox has no Internet).

Interface: check_agent_task, http_snapshot, BridgeFetchError, FetchSnapshot.
"""

import base64
import binascii
import logging
import re
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

from nfactory_core.config import Settings
from nfactory_core.events.redaction import redact
from nfactory_core.local_bridge import bridge_token
from nfactory_core.models import AgentCheck
from nfactory_core.models.base import utcnow
from nfactory_core.secrets import SecretStore
from nfactory_core.workspace import UnsafePathError, Workspace
from nfactory_worker.jobs.reporting import Sessions
from nfactory_worker.recipes.checks import JUNIT_PATH, pytest_check
from nfactory_worker.runner import JUnitError, Runner, parse_junit

log = logging.getLogger("nfactory.worker.agent_checks")
FetchSnapshot = Callable[[str, str], Awaitable[dict[str, Any]]]
_PYTHON_TEST = re.compile(r"(^|/)(test_[^/]*|[^/]*_test)\.py$")
MAX_FAILURES = 20
OUTPUT_TAIL = 4_000


class BridgeFetchError(RuntimeError):
    """The bridge did not hand over the files; message in French."""


async def check_agent_task(
    sessions: Sessions,
    settings: Settings,
    runner: Runner,
    check_id: str,
    *,
    fetch: FetchSnapshot | None = None,
) -> str:
    """Run the check and store its verdict; returns the final status."""
    async with sessions() as session:
        check = await session.get_one(AgentCheck, check_id)
        check.status = "running"
        token = await bridge_token(
            session,
            check.workspace_id,
            SecretStore(settings.nfactory_secret_key.get_secret_value()),
        )
        task_id = check.task_id
        await session.commit()

    if token is None:
        return await _finish(sessions, check_id, "error", "Le pont local n'est plus associé.")
    try:
        snapshot = await (fetch or http_snapshot(settings.nfactory_bridge_url))(token, task_id)
        files = _decoded(snapshot)
    except BridgeFetchError as exc:
        return await _finish(sessions, check_id, "error", str(exc))

    if not any(_PYTHON_TEST.search(path) for path in files):
        return await _finish(
            sessions,
            check_id,
            "not_tested",
            "Aucun test pytest trouvé : NFactory ne sait tester que les projets pytest pour "
            "l'instant.",
        )

    base = Path(settings.workspace_root)
    try:
        workspace = Workspace.create(base, check_id)
        workspace.write_files(files)
        return await _run_tests(sessions, runner, workspace, check_id)
    except UnsafePathError:
        return await _finish(sessions, check_id, "error", "Chemin de fichier refusé dans la tâche.")
    except Exception as exc:  # the sandbox may be down: say so, never fake a verdict
        log.exception("agent check %s failed", check_id)
        return await _finish(sessions, check_id, "error", f"Test impossible : {type(exc).__name__}")
    finally:
        shutil.rmtree(base / check_id, ignore_errors=True)


async def _run_tests(
    sessions: Sessions, runner: Runner, workspace: Workspace, check_id: str
) -> str:
    check = pytest_check()
    result = await runner.run(workspace.root.name, check.argv, check.timeout_s)
    output = str(redact((result.stdout + "\n" + result.stderr).strip()))[-OUTPUT_TAIL:]
    report: dict[str, Any] = {
        "command": " ".join(check.argv),
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "duration_s": round(result.duration_s, 2),
        "output_tail": output,
    }
    try:
        tests = parse_junit(workspace.read_text(JUNIT_PATH))
    except (OSError, UnsafePathError, JUnitError):
        report.update(passed=0, failed=0, errors=0, skipped=0, failures=[])
        return await _finish(
            sessions, check_id, "failed", "pytest n'a produit aucun rapport de tests.", report
        )
    report.update(
        passed=tests.passed,
        failed=tests.failed,
        errors=tests.errors,
        skipped=tests.skipped,
        failures=[
            {"name": f.name[:300], "message": str(redact(f.message))[:500]}
            for f in tests.failures[:MAX_FAILURES]
        ],
    )
    status = "passed" if tests.ok and result.exit_code == 0 else "failed"
    return await _finish(sessions, check_id, status, "", report)


async def _finish(
    sessions: Sessions,
    check_id: str,
    status: str,
    error: str,
    report: dict[str, Any] | None = None,
) -> str:
    async with sessions() as session:
        check = await session.get_one(AgentCheck, check_id)
        check.status, check.error, check.report = status, error[:1000], report
        check.finished_at = utcnow()
        await session.commit()
    return status


def _decoded(snapshot: Any) -> dict[str, bytes]:
    items = snapshot.get("files") if isinstance(snapshot, dict) else None
    if not isinstance(items, list):
        raise BridgeFetchError("Réponse du pont local inattendue.")
    files: dict[str, bytes] = {}
    for item in items:
        path = item.get("path") if isinstance(item, dict) else None
        data = item.get("data") if isinstance(item, dict) else None
        if not isinstance(path, str) or not isinstance(data, str):
            raise BridgeFetchError("Réponse du pont local inattendue.")
        try:
            files[path] = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise BridgeFetchError("Réponse du pont local inattendue.") from exc
    return files


def http_snapshot(bridge_url: str) -> FetchSnapshot:
    """Read a finished task's files from the paired bridge."""
    base = bridge_url.rstrip("/")

    async def fetch(token: str, task_id: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.get(
                    f"{base}/tasks/{task_id}/snapshot",
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.HTTPError as exc:
            raise BridgeFetchError(
                "Pont local non joignable : lancez ./scripts/bridge.ps1 sur cet ordinateur."
            ) from exc
        if response.status_code == 401:
            raise BridgeFetchError("Le pont ne reconnaît plus NFactory : réassociez-le.")
        if response.status_code != 200:
            raise BridgeFetchError(_bridge_message(response))
        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise BridgeFetchError("Réponse du pont local inattendue.") from exc
        return data

    return fetch


def _bridge_message(response: httpx.Response) -> str:
    try:
        message = response.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        message = None
    if isinstance(message, str) and message:
        return message[:300]
    return f"Le pont local a refusé la demande ({response.status_code})."
