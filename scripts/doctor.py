"""NFactory environment diagnostics (spec §17.2). Standard library only.

Usage: python scripts/doctor.py

Reports which tools and services are available. It never reads credential files and
never prints a token or key value: only "present" / "absent" and public version strings.
"""

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass

Runner = Callable[[list[str]], tuple[int, str]]

API_KEYS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "ZAI_API_KEY",
    "MOONSHOT_API_KEY",
    "DASHSCOPE_API_KEY",
    "MINIMAX_API_KEY",
)


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # ok | warn | missing | error
    detail: str


def run_command(cmd: list[str]) -> tuple[int, str]:
    # Resolve the full path: on Windows, npm tools are .CMD shims that CreateProcess
    # only finds by full path.
    executable = shutil.which(cmd[0])
    if executable is None:
        return 127, ""
    try:
        done = subprocess.run(  # noqa: S603 - fixed argument lists, no shell
            [executable, *cmd[1:]], capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, type(exc).__name__
    return done.returncode, (done.stdout + done.stderr).strip()


def check_tool(name: str, cmd: list[str], run: Runner = run_command) -> Check:
    code, out = run(cmd)
    if code == 127:
        return Check(name, "missing", "non installé")
    if code != 0:
        return Check(name, "error", f"code de sortie {code}")
    return Check(name, "ok", out.splitlines()[0] if out else "installé")


def check_gh_auth(run: Runner = run_command) -> Check:
    code, out = run(["gh", "auth", "status"])
    if code == 127:
        return Check("gh auth", "missing", "gh non installé (requis en phase 4)")
    if code != 0 or "Logged in" not in out:
        return Check("gh auth", "warn", "non connecté — lancer : gh auth login")
    # Only the account line is kept; token lines are dropped entirely.
    account = next((line.strip(" ✓-") for line in out.splitlines() if "Logged in" in line), "")
    return Check("gh auth", "ok", account)


def check_api_keys(env: Mapping[str, str]) -> Check:
    present = [key for key in API_KEYS if env.get(key)]
    if not present:
        return Check("Clés API", "warn", "aucune (mode démo sans clé)")
    return Check("Clés API", "ok", "présentes : " + ", ".join(present))


def check_http(name: str, url: str) -> Check:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:  # noqa: S310 - local URLs only
            body = response.read().decode()
    except Exception as exc:
        return Check(name, "error", f"injoignable ({type(exc).__name__})")
    try:
        status = json.loads(body).get("status", "ok")
    except ValueError:
        status = "ok"
    return Check(name, "ok" if status == "ok" else "warn", f"{url} → {status}")


def collect() -> list[Check]:
    return [
        check_tool("Docker", ["docker", "--version"]),
        check_tool("Docker Compose", ["docker", "compose", "version"]),
        check_tool("uv", ["uv", "--version"]),
        check_tool("Node.js", ["node", "--version"]),
        check_tool("git", ["git", "--version"]),
        check_tool("gh", ["gh", "--version"]),
        check_gh_auth(),
        check_tool("Codex CLI", ["codex", "--version"]),
        check_tool("Claude Code", ["claude", "--version"]),
        check_api_keys(os.environ),
        check_http("API /ready", "http://127.0.0.1:8000/api/v1/ready"),
        check_http("Dashboard", "http://127.0.0.1:3000/api/v1/health"),
    ]


ICONS = {"ok": "✓", "warn": "!", "missing": "–", "error": "✕"}  # noqa: RUF001 - glyphs on purpose


def main() -> int:
    checks = collect()
    width = max(len(c.name) for c in checks)
    for c in checks:
        print(f"{ICONS[c.status]} {c.name.ljust(width)}  {c.detail}")
    return 1 if any(c.status == "error" for c in checks) else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
