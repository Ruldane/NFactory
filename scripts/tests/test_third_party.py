"""third_party.py lists every shipped component with its licence and refuses strong copyleft."""

import importlib.metadata
import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "third_party", Path(__file__).resolve().parent.parent / "third_party.py"
)
assert _spec and _spec.loader
third_party = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(third_party)


@pytest.mark.parametrize(
    "expression",
    [
        "GPL-3.0-only",
        "AGPL-3.0-or-later",
        "MIT AND GPL-2.0-only",
        "(GPL-2.0-only OR AGPL-3.0-only)",
        "GNU General Public License v3 (GPLv3)",
        "GNU Affero General Public License v3",
        "SSPL-1.0",
    ],
)
def test_strong_copyleft_is_blocked(expression: str) -> None:
    assert third_party.is_blocked(expression)


@pytest.mark.parametrize(
    "expression",
    [
        "MIT",
        "LGPL-3.0-or-later",
        "GNU Lesser General Public License v3 (LGPLv3)",
        "GNU Library or Lesser General Public License (LGPL)",
        "MIT OR GPL-2.0-only",
        "MPL-2.0",
        "",
    ],
)
def test_permissive_weak_copyleft_and_dual_licences_pass(expression: str) -> None:
    assert not third_party.is_blocked(expression)


def _dist_info(root: Path, name: str, version: str, headers: list[str], license_text: str = ""):
    info = root / f"{name.replace('-', '_')}-{version}.dist-info"
    info.mkdir(parents=True)
    lines = ["Metadata-Version: 2.4", f"Name: {name}", f"Version: {version}", *headers]
    (info / "METADATA").write_text("\n".join(lines) + "\n", encoding="utf-8")
    record = [f"{info.name}/METADATA,,"]
    if license_text:
        (info / "licenses").mkdir()
        (info / "licenses" / "LICENSE").write_text(license_text, encoding="utf-8")
        record.append(f"{info.name}/licenses/LICENSE,,")
    (info / "RECORD").write_text("\n".join(record) + "\n", encoding="utf-8")


def test_python_components_read_installed_metadata(tmp_path: Path) -> None:
    _dist_info(
        tmp_path, "alpha", "1.0", ["License-Expression: MIT", "License: ignored"], "Alpha licence"
    )
    _dist_info(
        tmp_path,
        "beta",
        "2.0",
        ["Classifier: License :: OSI Approved :: Apache Software License"],
    )
    _dist_info(tmp_path, "gamma", "3.0", ["License: " + "long licence text " * 20])
    _dist_info(tmp_path, "nfactory-core", "0.1.0", ["License-Expression: MIT"])

    found = third_party.python_components(
        importlib.metadata.distributions(path=[str(tmp_path)]), group="Python"
    )

    by_name = {c.name: c for c in found}
    assert set(by_name) == {"alpha", "beta", "gamma"}  # NFactory's own packages are not third-party
    assert by_name["alpha"].license == "MIT"
    assert by_name["alpha"].texts == (("LICENSE", "Alpha licence"),)
    assert by_name["beta"].license == "Apache Software License"
    assert by_name["gamma"].license == ""  # a whole licence pasted in the field is not an id


def _lockfile(packages: dict) -> dict:
    return {"lockfileVersion": 3, "packages": {"": {"name": "app"}, **packages}}


def test_npm_components_follow_the_lockfile(tmp_path: Path) -> None:
    (tmp_path / "node_modules" / "react").mkdir(parents=True)
    (tmp_path / "node_modules" / "react" / "LICENSE").write_text("React licence", encoding="utf-8")
    lock = _lockfile(
        {
            "node_modules/react": {"version": "19.3.1", "license": "MIT"},
            "node_modules/vitest": {"version": "5.0.5", "license": "MIT", "dev": True},
            "node_modules/old": {"version": "0.1.0", "license": {"type": "BSD-2-Clause"}},
            "node_modules/a/node_modules/react": {"version": "19.3.1", "license": "MIT"},
            "node_modules/local": {"resolved": "../local", "link": True},
            "node_modules/@scope/none": {"version": "1.0.0"},
        }
    )

    prod = third_party.npm_components(lock, tmp_path, group="Dashboard", include_dev=False)
    every = third_party.npm_components(lock, tmp_path, group="Dashboard", include_dev=True)

    assert [(c.name, c.version, c.license) for c in prod] == [
        ("@scope/none", "1.0.0", ""),
        ("old", "0.1.0", "BSD-2-Clause"),
        ("react", "19.3.1", "MIT"),
    ]
    assert prod[2].texts == (("LICENSE", "React licence"),)
    assert "vitest" in {c.name for c in every}


def test_notices_are_deterministic_and_fence_licence_texts() -> None:
    components = [
        third_party.Component("Dashboard", "zeta", "1.0", "MIT", (("LICENSE", "has ``` inside"),)),
        third_party.Component("Dashboard", "alpha", "2.0", "", ()),
    ]

    text = third_party.render(components)

    assert text == third_party.render(list(reversed(components)))
    assert text.index("alpha") < text.index("zeta")
    assert "| MIT | 1 |" in text
    assert "non déclarée" in text
    assert "````text\nhas ``` inside\n````" in text


def _repo(root: Path, dashboard_packages: dict) -> None:
    for folder, packages in (
        ("apps/dashboard", dashboard_packages),
        ("apps/sandbox/web-deps", {"node_modules/vite": {"version": "8.3.5", "license": "MIT"}}),
    ):
        (root / folder).mkdir(parents=True)
        (root / folder / "package-lock.json").write_text(
            json.dumps(_lockfile(packages)), encoding="utf-8"
        )


def test_main_writes_the_notices_for_the_installed_environment(tmp_path: Path) -> None:
    _repo(tmp_path, {"node_modules/react": {"version": "19.3.1", "license": "MIT"}})
    out = tmp_path / "THIRD_PARTY_NOTICES.md"

    code = third_party.main(["--root", str(tmp_path), "--out", str(out)])

    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "react" in text and "vite" in text and "fastapi" in text


def test_main_fails_and_names_a_blocked_component(tmp_path: Path, capsys) -> None:
    _repo(tmp_path, {"node_modules/viral": {"version": "1.0.0", "license": "GPL-3.0-only"}})

    code = third_party.main(["--root", str(tmp_path), "--out", str(tmp_path / "n.md")])

    assert code == 1
    assert "viral 1.0.0 (GPL-3.0-only)" in capsys.readouterr().err
