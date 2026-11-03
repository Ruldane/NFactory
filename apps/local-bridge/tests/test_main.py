"""Starting the bridge: loopback port, store in the user's profile, a code when needed."""

import subprocess
from pathlib import Path

from nfactory_bridge.__main__ import DEFAULT_PORT, start


def test_an_unpaired_bridge_shows_a_pairing_code(tmp_path: Path) -> None:
    lines: list[str] = []

    server, pairing = start(["--port", "0", "--store", str(tmp_path / "b.json")], lines.append)
    try:
        assert server.server_address[0] == "127.0.0.1"
        assert any("Code d'appairage" in line for line in lines)
        assert not pairing.paired
    finally:
        server.server_close()


def test_a_paired_bridge_shows_no_code_unless_asked(tmp_path: Path) -> None:
    store = tmp_path / "b.json"
    first, pairing = start(["--port", "0", "--store", str(store)], lambda _: None)
    pairing.pair(pairing.new_code())
    first.server_close()

    quiet: list[str] = []
    second, _ = start(["--port", "0", "--store", str(store)], quiet.append)
    second.server_close()
    asked: list[str] = []
    third, _ = start(["--port", "0", "--store", str(store), "--pair"], asked.append)
    third.server_close()

    assert not any("Code d'appairage" in line for line in quiet)
    assert any("Code d'appairage" in line for line in asked)


def test_the_default_port() -> None:
    assert DEFAULT_PORT == 8765


def test_its_messages_print_in_a_windows_console(tmp_path: Path) -> None:
    # PowerShell 5.1 and redirected output use cp1252: a character outside it crashes print.
    lines: list[str] = []
    server, _ = start(["--port", "0", "--store", str(tmp_path / "b.json")], lines.append)
    server.server_close()

    for line in lines:
        line.encode("cp1252")


def git_repo(path: Path) -> Path:
    import subprocess

    path.mkdir(parents=True)
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    return path


def test_allow_and_revoke_manage_the_repositories(tmp_path: Path) -> None:
    from nfactory_bridge.__main__ import manage

    store = tmp_path / "profile" / "bridge.json"
    repo = git_repo(tmp_path / "nfactory-test")
    lines: list[str] = []

    assert manage(["--store", str(store), "--allow", str(repo)], lines.append)
    assert manage(["--store", str(store), "--repos"], lines.append)
    assert manage(["--store", str(store), "--revoke", "nfactory-test"], lines.append)

    assert any("nfactory-test" in line and "autorisé" in line for line in lines)
    assert (tmp_path / "profile" / "repos.json").exists()


def test_without_an_admin_option_the_bridge_starts(tmp_path: Path) -> None:
    from nfactory_bridge.__main__ import manage

    assert not manage(["--store", str(tmp_path / "b.json")], lambda _: None)


def test_codex_must_be_connected_before_a_task(tmp_path: Path) -> None:
    import pytest

    from nfactory_bridge.__main__ import codex_resolver
    from nfactory_bridge.tasks import TaskRefused

    def status(value: str):
        return lambda: {"kind": "codex", "status": value}

    with pytest.raises(TaskRefused) as missing:
        codex_resolver(lambda name: None, status("not_installed"))()
    with pytest.raises(TaskRefused) as logged_out:
        codex_resolver(lambda name: "C:/codex.exe", status("needs_login"))()

    assert missing.value.code == "not_installed"
    assert logged_out.value.code == "needs_login"
    assert "codex login" in str(logged_out.value)
    assert codex_resolver(lambda name: "C:/codex.exe", status("connected"))() == "C:/codex.exe"


def test_handoff_prints_how_to_run_claude_and_never_runs_it(tmp_path: Path) -> None:
    from nfactory_bridge.__main__ import manage

    store = tmp_path / "profile" / "bridge.json"
    task_dir = tmp_path / "profile" / "worktrees" / "nfactory-test" / "t_0123456789ab"
    task_dir.mkdir(parents=True)
    (task_dir.parent / "t_0123456789ab.brief.md").write_text("# brief", encoding="utf-8")
    lines: list[str] = []

    assert manage(["--store", str(store), "--handoff", "t_0123456789ab"], lines.append)
    assert manage(["--store", str(store), "--handoff", "t_ffffffffffff"], lines.append)

    assert any(str(task_dir) in line for line in lines)
    assert any("claude" in line for line in lines)
    assert "Relais inconnu" in lines[-1]


def test_allow_push_names_the_github_repository(tmp_path: Path) -> None:
    from nfactory_bridge.__main__ import manage

    store = tmp_path / "profile" / "bridge.json"
    repo = git_repo(tmp_path / "nfactory-test")
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "remote",
            "add",
            "origin",
            "https://github.com/Ruldane/nfactory-test.git",
        ],
        check=True,
    )
    lines: list[str] = []

    manage(["--store", str(store), "--allow", str(repo)], lines.append)
    assert manage(["--store", str(store), "--allow-push", "nfactory-test"], lines.append)
    manage(["--store", str(store), "--allow-push", "unknown"], lines.append)

    assert any("Ruldane/nfactory-test" in line for line in lines)
    assert lines[-1].startswith("Refusé")
