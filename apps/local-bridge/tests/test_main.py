"""Starting the bridge: loopback port, store in the user's profile, a code when needed."""

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
