"""Deterministic secret scan of a generated workspace (A10, spec §8.3).

A finding names the file, the line and the rule, never the value: it goes into
events, logs and the debugger's prompt.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath

MAX_FILE_BYTES = 2_000_000

_TOKEN_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key", re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_\w{60,})")),
    (
        "api-key",
        re.compile(
            r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}"
            r"|\bAIza[0-9A-Za-z_-]{35}"
            r"|\bxox[abprs]-[A-Za-z0-9-]{10,}"
        ),
    ),
)
# key = "value" / "key": "value", where the key names a secret.
_ASSIGNED = re.compile(
    r"(?i)[\w-]*(?:password|passwd|secret|api_?key|token|access_?key|private_?key)[\w-]*"
    r"[\"']?\s*[:=]\s*(?P<quote>[\"'])(?P<value>[^\"'\n]{8,})(?P=quote)"
)
_URL_CREDENTIALS = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@<>]+:(?P<value>[^\s@/]{3,})@")
_PLACEHOLDER_WORDS = (
    "change",
    "example",
    "exemple",
    "votre",
    "your",
    "dummy",
    "placeholder",
    "redacted",
)
_LABELS = {
    "private-key": "clé privée",
    "aws-access-key": "clé d'accès AWS",
    "github-token": "jeton GitHub",
    "api-key": "clé d'API",
    "assigned-secret": "secret écrit en clair",
    "url-credentials": "identifiants dans une URL",
    "env-file": "fichier .env rempli",
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str

    @property
    def message(self) -> str:
        return f"{self.path}:{self.line} : {_LABELS[self.rule]} probable (valeur masquée)"


def scan_files(files: Mapping[str, str | bytes]) -> list[Finding]:
    findings: list[Finding] = []
    for path, content in files.items():
        text = _as_text(content)
        if text is None:
            continue
        if _is_env_file(path):
            findings.extend(_scan_env(path, text))
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            rule = _rule_for(line)
            if rule:
                findings.append(Finding(path, number, rule))
    return sorted(findings, key=lambda f: (f.path, f.line))


def _rule_for(line: str) -> str | None:
    for rule, pattern in _TOKEN_RULES:
        if pattern.search(line):
            return rule
    for match in _ASSIGNED.finditer(line):
        if not _placeholder(match.group("value")):
            return "assigned-secret"
    for match in _URL_CREDENTIALS.finditer(line):
        if not _placeholder(match.group("value")):
            return "url-credentials"
    return None


def _placeholder(value: str) -> bool:
    lowered = value.lower()
    return (
        any(mark in value for mark in ("<", "${", "{{", "%("))
        or len(set(lowered)) <= 2
        or any(word in lowered for word in _PLACEHOLDER_WORDS)
    )


def _is_env_file(path: str) -> bool:
    name = PurePosixPath(path).name
    return name == ".env" or (
        name.startswith(".env.") and not name.endswith((".example", ".sample", ".template"))
    )


def _scan_env(path: str, text: str) -> list[Finding]:
    """One finding per filled .env file: it should never be delivered."""
    for number, line in enumerate(text.splitlines(), start=1):
        key, sep, value = line.partition("=")
        if sep and key.strip() and not key.lstrip().startswith("#") and value.strip():
            if not _placeholder(value.strip()) and _ASSIGNED_KEY.search(key):
                return [Finding(path, number, "env-file")]
    return []


_ASSIGNED_KEY = re.compile(r"(?i)password|passwd|secret|api_?key|token|access_?key|private_?key")


def _as_text(content: str | bytes) -> str | None:
    if isinstance(content, bytes):
        if len(content) > MAX_FILE_BYTES or b"\x00" in content[:8192]:
            return None
        content = content.decode("utf-8", "replace")
    return None if len(content) > MAX_FILE_BYTES else content
