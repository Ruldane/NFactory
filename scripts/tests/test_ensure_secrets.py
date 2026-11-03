"""ensure_secrets fills generated secrets into .env without ever printing them."""

import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "ensure_secrets", Path(__file__).resolve().parent.parent / "ensure_secrets.py"
)
assert _spec and _spec.loader
ensure_secrets = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ensure_secrets)

EXAMPLE = (
    "NFACTORY_DEMO_MODE=true\n"
    "NFACTORY_SESSION_SECRET=\nNFACTORY_SECRET_KEY=\nNFACTORY_SANDBOX_TOKEN=\n"
)


def values(env: Path) -> dict[str, str]:
    lines = env.read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line)


def test_creates_env_from_example_with_fresh_secrets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".env.example").write_text(EXAMPLE, encoding="utf-8")

    filled = ensure_secrets.ensure(tmp_path)

    env = values(tmp_path / ".env")
    assert sorted(filled) == sorted(ensure_secrets.GENERATED)
    assert all(len(env[name]) >= 32 for name in ensure_secrets.GENERATED)
    assert env["NFACTORY_DEMO_MODE"] == "true"
    printed = capsys.readouterr().out
    assert not any(env[name] in printed for name in ensure_secrets.GENERATED)


def test_keeps_existing_values_and_adds_only_missing_ones(tmp_path: Path) -> None:
    (tmp_path / ".env.example").write_text(EXAMPLE, encoding="utf-8")
    (tmp_path / ".env").write_text(
        "NFACTORY_SESSION_SECRET=keep-me-keep-me-keep-me-keep-me-1\nOTHER=1\n", encoding="utf-8"
    )

    filled = ensure_secrets.ensure(tmp_path)

    env = values(tmp_path / ".env")
    assert env["NFACTORY_SESSION_SECRET"] == "keep-me-keep-me-keep-me-keep-me-1"
    assert env["OTHER"] == "1"
    assert "NFACTORY_SANDBOX_TOKEN" in filled and len(env["NFACTORY_SANDBOX_TOKEN"]) >= 32
    assert ensure_secrets.ensure(tmp_path) == []  # idempotent
