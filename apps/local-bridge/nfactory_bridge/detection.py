"""Detection of the local coding tools: OpenAI Codex CLI, Claude Code, GitHub CLI.

Only public commands run (`--version`, then each tool's own login status command). The bridge
never opens an auth file, a cookie or a token: the official binary reads its own state and
answers. Raw outputs stay here; only a status, a version and a login method leave.

Statuses: not_installed, installed (status unknown), needs_login, connected.
`modes` says what NFactory may do with a tool; Claude Code is handoff only (spec §6.5).
Interface: detect(which, run) -> list of runtimes; newest and which_all (the install to use
when several are on the PATH); Completed; run_command (the real runner).
"""

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

STATUS_TIMEOUT_S = 15.0
_VERSION = re.compile(r"\d+\.\d+(?:\.\d+)?")


@dataclass(frozen=True)
class Completed:
    code: int
    stdout: str
    stderr: str = ""

    @property
    def text(self) -> str:
        """Both streams: codex and gh print their login status on stderr."""
        return " ".join((self.stdout, self.stderr))


Which = Callable[[str], str | None]
Run = Callable[[list[str], float], Completed]


@dataclass(frozen=True)
class _Tool:
    kind: str
    label: str
    status_args: tuple[str, ...]
    login_command: str
    modes: dict[str, str]


_TOOLS = (
    _Tool(
        "codex", "OpenAI Codex CLI", ("login", "status"), "codex login", {"runtime": "available"}
    ),
    _Tool(
        "claude",
        "Claude Code",
        ("auth", "status", "--json"),
        "claude auth login",
        {"handoff": "available", "runtime": "blocked_by_policy"},
    ),
    _Tool("gh", "GitHub CLI", ("auth", "status"), "gh auth login", {}),
)


def run_command(argv: list[str], timeout_s: float) -> Completed:
    """Run one fixed command of an official tool, without a shell or any input."""
    done = subprocess.run(  # noqa: S603 - argv is fixed by _TOOLS and resolved by `which`
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    return Completed(done.returncode, done.stdout, done.stderr)


def which_all(name: str, path: str | None = None) -> list[str]:
    """Every install of `name` on the PATH, in PATH order."""
    found: list[str] = []
    for folder in (path if path is not None else os.environ.get("PATH", "")).split(os.pathsep):
        hit = shutil.which(name, path=folder) if folder else None
        if hit and hit not in found:
            found.append(hit)
    return found


def newest(
    name: str,
    *,
    candidates: Callable[[str], list[str]] = which_all,
    run: Run = run_command,
) -> str | None:
    """The install with the highest `--version`: an old copy first in the PATH (an npm
    shim next to a current app, say) must not shadow the one the user keeps up to date."""
    paths = candidates(name)
    if len(paths) <= 1:
        return paths[0] if paths else None
    ranked: list[tuple[tuple[int, ...], int, str]] = []
    for order, candidate in enumerate(paths):
        try:
            match = _VERSION.search(run([candidate, "--version"], STATUS_TIMEOUT_S).stdout)
        except (OSError, subprocess.TimeoutExpired):
            match = None
        version = tuple(int(part) for part in match.group(0).split(".")) if match else ()
        ranked.append((version, -order, candidate))
    return max(ranked)[2]


def detect(which: Which = newest, run: Run = run_command) -> list[dict[str, Any]]:
    return [_detect(tool, which, run) for tool in _TOOLS]


def _detect(tool: _Tool, which: Which, run: Run) -> dict[str, Any]:
    found: dict[str, Any] = {
        "kind": tool.kind,
        "label": tool.label,
        "status": "not_installed",
        "version": None,
        "login": None,
        "login_command": tool.login_command,
        "modes": {},
        "detail": "",
    }
    path = which(tool.kind)
    if path is None:
        found["detail"] = f"« {tool.kind} » introuvable dans le PATH."
        return found
    found["status"] = "installed"
    found["modes"] = dict(tool.modes)
    try:
        version = run([path, "--version"], STATUS_TIMEOUT_S)
        match = _VERSION.search(version.stdout)
        found["version"] = match.group(0) if match else None
        status = run([path, *tool.status_args], STATUS_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        found["detail"] = "Statut indisponible : délai dépassé."
        return found
    except OSError:
        found["detail"] = "Statut indisponible : l'outil n'a pas pu être lancé."
        return found
    logged_in, login = _LOGIN_PARSERS[tool.kind](status)
    if logged_in is None:
        found["detail"] = "Statut de connexion illisible."
    else:
        found["status"] = "connected" if logged_in else "needs_login"
        found["login"] = login if logged_in else None
    return found


def _codex_login(status: Completed) -> tuple[bool | None, str | None]:
    if status.code != 0:
        return False, None
    text = status.text.lower()
    return True, "chatgpt" if "chatgpt" in text else "api_key" if "api key" in text else None


def _claude_login(status: Completed) -> tuple[bool | None, str | None]:
    try:
        data = json.loads(status.stdout)
    except ValueError:
        return None, None
    logged_in = data.get("loggedIn") if isinstance(data, dict) else None
    if not isinstance(logged_in, bool):
        return None, None
    return logged_in, None  # account, organisation and plan stay on the machine


def _gh_login(status: Completed) -> tuple[bool | None, str | None]:
    return status.code == 0, None


_LOGIN_PARSERS = {"codex": _codex_login, "claude": _claude_login, "gh": _gh_login}
