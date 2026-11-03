"""Tiny, strict template renderer for recipe files.

`{{name}}` placeholders never clash with Python, JSON or Markdown syntax. Rendering
fails if a placeholder has no value or a value is never used, so a typo cannot ship
a half-rendered project.
"""

import re
from collections.abc import Mapping
from importlib import resources

_PLACEHOLDER = re.compile(r"\{\{([a-z_][a-z0-9_]*)\}\}")


class TemplateError(ValueError):
    pass


def render_template(template: str, values: Mapping[str, str]) -> str:
    used = set(_PLACEHOLDER.findall(template))
    missing = used - values.keys()
    if missing:
        raise TemplateError(f"Missing template values: {sorted(missing)}")
    unused = values.keys() - used
    if unused:
        raise TemplateError(f"Unused template values: {sorted(unused)}")
    return _PLACEHOLDER.sub(lambda m: values[m.group(1)], template)


def load_template(package: str, name: str) -> str:
    """Read `templates/<name>.tmpl` shipped inside a recipe package."""
    return (resources.files(package) / "templates" / f"{name}.tmpl").read_text(encoding="utf-8")


def py_literal(text: str) -> str:
    """A Python string literal for arbitrary text: inert, whatever the text contains."""
    return repr(text)


# Characters PowerShell accepts as a single quote: each one is escaped by doubling it.
_PS_QUOTES = "'\u2018\u2019\u201a\u201b"


def ps_literal(text: str) -> str:
    """A PowerShell single-quoted literal: no variable or subexpression is ever expanded."""
    escaped = "".join(ch * 2 if ch in _PS_QUOTES else ch for ch in text)
    return f"'{escaped}'"


def ps_comment(text: str) -> str:
    """One line of text that cannot end (or open) a PowerShell block comment."""
    flat = " ".join(text.split())
    return flat.replace("#>", "# >").replace("<#", "< #")
