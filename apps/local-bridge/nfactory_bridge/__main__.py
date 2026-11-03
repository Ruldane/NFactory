"""Run the bridge on the user's machine (outside Docker): scripts/bridge.ps1 or
scripts/bridge.sh, which run `python -m nfactory_bridge` from apps/local-bridge.

Options: --port (default 8765), --store (pairing file), --pair (show a new pairing code).
Repository admin, run by the user in their own terminal, then exit: --allow <folder>,
--revoke <id>, --repos, --allow-push <id> (publish to its GitHub origin), and
--handoff <task-id> (how to run Claude Code on a handoff).
Every file (pairing hash, authorized repositories, worktrees)
lives in the user's profile, out of any repository.
"""

import argparse
import os
import sys
from collections.abc import Callable
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from nfactory_bridge import __version__
from nfactory_bridge.detection import Which, detect, newest
from nfactory_bridge.github import GitHub, GitHubRefused
from nfactory_bridge.pairing import CODE_TTL_S, Pairing
from nfactory_bridge.repos import RepoRefused, RepoRegistry
from nfactory_bridge.server import make_server
from nfactory_bridge.tasks import TaskRefused, Tasks, handoff_instructions

DEFAULT_PORT = 8765
HOST = "127.0.0.1"


def default_store() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.join(Path.home(), ".config")
    return Path(base) / "NFactory" / "bridge.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nfactory-bridge", description="Pont local NFactory")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--store", type=Path, default=default_store())
    parser.add_argument("--pair", action="store_true", help="afficher un nouveau code")
    parser.add_argument("--allow", type=Path, help="autoriser un dépôt Git pour NFactory")
    parser.add_argument("--revoke", help="retirer un dépôt autorisé (son identifiant)")
    parser.add_argument("--repos", action="store_true", help="lister les dépôts autorisés")
    parser.add_argument("--handoff", help="afficher comment lancer Claude Code sur un relais")
    parser.add_argument("--allow-push", help="autoriser la publication GitHub d'un dépôt (son id)")
    return parser


def manage(argv: list[str], say: Callable[[str], None]) -> bool:
    """Run a repository admin option; False when there is none (start the bridge)."""
    args = _parser().parse_args(argv)
    if not (args.allow or args.revoke or args.repos or args.handoff or args.allow_push):
        return False
    if args.handoff:
        lines = handoff_instructions(args.store.parent / "worktrees", args.handoff)
        for line in lines or [f"Relais inconnu sur ce poste : {args.handoff}"]:
            say(line)
        return True
    registry = RepoRegistry(args.store.parent / "repos.json")
    if args.allow:
        try:
            repo = registry.allow(args.allow)
        except RepoRefused as exc:
            say(f"Refusé : {exc}")
            return True
        say(f"Dépôt autorisé : {repo.id} ({repo.path})")
    if args.allow_push:
        try:
            repo = registry.allow_push(args.allow_push)
        except RepoRefused as exc:
            say(f"Refusé : {exc}")
            return True
        say(
            f"Publication autorisée : {repo.id} → github.com/{repo.github} (PR brouillon seulement)"
        )
    if args.revoke:
        registry.revoke(args.revoke)
        say(f"Dépôt retiré : {args.revoke}")
    if args.repos:
        repos = registry.all()
        say("Dépôts autorisés :" if repos else "Aucun dépôt autorisé.")
        for repo in repos:
            target = f"  → github.com/{repo.github}" if repo.github else ""
        say(f"  {repo.id}  {repo.path}{target}")
    return True


def codex_resolver(which: Which, status: Callable[[], dict[str, Any]]) -> Callable[[], str]:
    """The Codex executable to run, once Codex is installed and logged in."""

    def resolve() -> str:
        path = which("codex")
        if path is None:
            raise TaskRefused("not_installed", "Codex n'est pas installé sur ce poste.")
        if status().get("status") != "connected":
            raise TaskRefused(
                "needs_login", "Codex n'est pas connecté : lancez « codex login » dans un terminal."
            )
        return path

    return resolve


def gh_resolver(which: Which, status: Callable[[], dict[str, Any]]) -> Callable[[], str]:
    """The gh executable, once GitHub CLI is installed and logged in."""

    def resolve() -> str:
        path = which("gh")
        if path is None:
            raise GitHubRefused("GitHub CLI (gh) n'est pas installé sur ce poste.", "not_installed")
        if status().get("status") != "connected":
            raise GitHubRefused(
                "GitHub CLI n'est pas connecté : lancez « gh auth login » dans un terminal.",
                "needs_login",
            )
        return path

    return resolve


def _gh_status() -> dict[str, Any]:
    return next(tool for tool in detect() if tool["kind"] == "gh")


def _codex_status() -> dict[str, Any]:
    return next(tool for tool in detect() if tool["kind"] == "codex")


def start(argv: list[str], say: Callable[[str], None]) -> tuple[ThreadingHTTPServer, Pairing]:
    args = _parser().parse_args(argv)
    pairing = Pairing(args.store)
    repos = RepoRegistry(args.store.parent / "repos.json")
    tasks = Tasks(
        repos,
        args.store.parent / "worktrees",
        codex=codex_resolver(newest, _codex_status),
        github=GitHub(gh=gh_resolver(newest, _gh_status)),
    )
    server = make_server(HOST, args.port, pairing=pairing, detect=detect, tasks=tasks, repos=repos)
    port = server.server_address[1]
    say(f"Pont local NFactory {__version__} : http://{HOST}:{port} (boucle locale uniquement)")
    if args.pair or not pairing.paired:
        code = pairing.new_code()
        minutes = CODE_TTL_S // 60
        say(f"Code d'appairage : {code} (valable {minutes} min, à saisir dans NFactory)")
        say("Dans NFactory : page Moteurs IA, section Outils locaux, Associer le pont.")
    else:
        say("Déjà associé à NFactory. Relancez avec --pair pour un nouveau code.")
    say(f"Dépôts autorisés : {len(repos.all())} (ajoutez-en avec --allow <dossier>).")
    return server, pairing


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        # A console that cannot show a character must not stop the bridge.
        sys.stdout.reconfigure(errors="replace")

    def say(line: str) -> None:
        print(line, flush=True)

    if manage(sys.argv[1:], say):
        return
    server, _ = start(sys.argv[1:], say)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Pont arrêté.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
