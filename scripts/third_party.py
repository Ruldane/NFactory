"""Third-party notices and the licence policy (legal review §6, CRA preparation).

Lists every component NFactory ships, with its licence and licence files:
- the Python environment (API, worker, and the sandbox's Python tools, all pinned by uv.lock);
- the dashboard's production npm packages (its lockfile);
- the sandbox's web toolchain (`apps/sandbox/web-deps`, all of it: generated apps build with it).

Writes `THIRD_PARTY_NOTICES.md` and exits 1 when a component is under strong copyleft only
(GPL, AGPL, SSPL): those would bind NFactory's own licence. LGPL and MPL are allowed as used.
Standard library only, so CI runs it in the synced environment: `uv run python
scripts/third_party.py`. The CycloneDX SBOMs come from `uv export` and `npm sbom` (see CI).
"""

import argparse
import importlib.metadata
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

PYTHON_GROUP = "Python (API, worker, outils Python du sandbox)"
NPM_GROUPS = (
    ("Dashboard (production)", "apps/dashboard", False),
    ("Outils web du sandbox", "apps/sandbox/web-deps", True),
)

_LICENCE_FILE = re.compile(r"^(licen[cs]e|copying|notice)", re.IGNORECASE)
_STRONG_COPYLEFT = re.compile(
    r"(?<![a-z])a?gpl|affero|(?<!lesser )(?<!library )general public license"
    r"|sspl|server side public license",
    re.IGNORECASE,
)
_MAX_TEXT = 64_000


@dataclass(frozen=True)
class Component:
    group: str
    name: str
    version: str
    license: str  # an SPDX expression or a classifier name; "" when undeclared
    texts: tuple[tuple[str, str], ...]  # (file name, content) of its licence files


def is_blocked(expression: str) -> bool:
    """True when every alternative of the expression is strong copyleft."""
    alternatives = re.split(r"\s+OR\s+", expression.replace("(", " ").replace(")", " ").strip())
    alternatives = [a for a in alternatives if a.strip()]
    return bool(alternatives) and all(_STRONG_COPYLEFT.search(a) for a in alternatives)


def _python_licence(metadata) -> str:
    expression = (metadata.get("License-Expression") or "").strip()
    if expression:
        return expression
    field = (metadata.get("License") or "").strip()
    if field and "\n" not in field and len(field) <= 60 and field.upper() != "UNKNOWN":
        return field
    names = [
        c.split(" :: ")[-1]
        for c in metadata.get_all("Classifier") or []
        if c.startswith("License :: ") and c.split(" :: ")[-1] != "OSI Approved"
    ]
    return " OR ".join(names)


def _read(path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:_MAX_TEXT]
    except OSError:
        return ""


def python_components(
    distributions: Iterable[importlib.metadata.Distribution], *, group: str
) -> list[Component]:
    found: dict[tuple[str, str], Component] = {}
    for dist in distributions:
        name = dist.metadata["Name"] or ""
        if not name or name.lower().replace("_", "-").startswith("nfactory"):
            continue  # NFactory's own workspace packages
        texts = tuple(
            (file.name, _read(Path(str(file.locate()))))
            for file in sorted(dist.files or [], key=str)
            if file.parts
            and file.parts[0].endswith(".dist-info")
            and _LICENCE_FILE.match(file.name)
        )
        key = (name.lower(), dist.version)
        found.setdefault(
            key, Component(group, name, dist.version, _python_licence(dist.metadata), texts)
        )
    return sorted(found.values(), key=lambda c: (c.name.lower(), c.version))


def npm_components(
    lockfile: Mapping, root: Path, *, group: str, include_dev: bool
) -> list[Component]:
    found: dict[tuple[str, str], Component] = {}
    for key, entry in (lockfile.get("packages") or {}).items():
        if not key or entry.get("link") or "version" not in entry:
            continue
        if entry.get("dev") and not include_dev:
            continue
        name = key.rsplit("node_modules/", 1)[-1]
        licence = entry.get("license", "")
        if isinstance(licence, Mapping):
            licence = licence.get("type", "")
        folder = root / key
        texts = (
            tuple(
                (p.name, _read(p))
                for p in sorted(folder.iterdir())
                if p.is_file() and _LICENCE_FILE.match(p.name)
            )
            if folder.is_dir()
            else ()
        )
        found.setdefault(
            (name, entry["version"]),
            Component(group, name, entry["version"], str(licence or ""), texts),
        )
    return sorted(found.values(), key=lambda c: (c.name.lower(), c.version))


def _label(component: Component) -> str:
    return component.license or "non déclarée"


def _fence(text: str) -> str:
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def render(components: Iterable[Component]) -> str:
    ordered = sorted(components, key=lambda c: (c.group, c.name.lower(), c.version))
    lines = [
        "# Composants tiers",
        "",
        "Fichier généré par `scripts/third_party.py` à partir des fichiers de verrouillage et des",
        "métadonnées installées. Ne pas le modifier à la main.",
        "",
        "## Résumé des licences",
        "",
        "| Licence | Composants |",
        "|---|---|",
    ]
    counts = Counter(_label(c) for c in ordered)
    lines += [
        f"| {name} | {n} |" for name, n in sorted(counts.items(), key=lambda i: (-i[1], i[0]))
    ]
    for group in dict.fromkeys(c.group for c in ordered):
        lines += ["", f"## {group}", "", "| Composant | Version | Licence |", "|---|---|---|"]
        lines += [f"| {c.name} | {c.version} | {_label(c)} |" for c in ordered if c.group == group]
    lines += ["", "## Textes de licence"]
    for c in ordered:
        for file_name, text in c.texts:
            fence = _fence(text)
            body = text.rstrip("\n")
            lines += ["", f"### {c.name} {c.version}, {file_name}", "", f"{fence}text", body, fence]
    return "\n".join(lines) + "\n"


def collect(root: Path) -> list[Component]:
    components = python_components(importlib.metadata.distributions(), group=PYTHON_GROUP)
    for group, folder, include_dev in NPM_GROUPS:
        lockfile = json.loads((root / folder / "package-lock.json").read_text(encoding="utf-8"))
        components += npm_components(lockfile, root / folder, group=group, include_dev=include_dev)
    return components


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    out = args.out or args.root / "THIRD_PARTY_NOTICES.md"

    components = collect(args.root)
    out.write_text(render(components), encoding="utf-8")
    blocked = [c for c in components if is_blocked(c.license)]
    for c in blocked:
        print(f"Licence refusée : {c.name} {c.version} ({c.license}), {c.group}", file=sys.stderr)
    undeclared = sum(1 for c in components if not c.license)
    print(
        f"{len(components)} composants, {undeclared} sans licence déclarée, "
        f"{len(blocked)} refusés -> {out}",
        file=sys.stderr,
    )
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
