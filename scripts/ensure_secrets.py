"""Create .env from .env.example and fill every generated local secret that is empty.

Existing values are never changed and secret values are never printed: only the names
of the secrets that were filled. Usage: python scripts/ensure_secrets.py
"""

import re
import secrets
import sys
from pathlib import Path

# name -> random bytes
GENERATED = {
    "NFACTORY_SESSION_SECRET": 48,
    "NFACTORY_SECRET_KEY": 32,
    "NFACTORY_SANDBOX_TOKEN": 32,
}


def ensure(root: Path) -> list[str]:
    env = root / ".env"
    if not env.exists():
        env.write_text((root / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
    text = env.read_text(encoding="utf-8")
    filled: list[str] = []
    for name, size in GENERATED.items():
        value = secrets.token_urlsafe(size)
        line = re.compile(rf"^{name}=(.*)$", re.MULTILINE)
        match = line.search(text)
        if match is None:
            text = text.rstrip("\n") + f"\n{name}={value}\n"
        elif not match.group(1).strip():
            text = text[: match.start()] + f"{name}={value}" + text[match.end() :]
        else:
            continue
        filled.append(name)
    if filled:
        env.write_text(text, encoding="utf-8")
    return filled


def main() -> None:
    filled = ensure(Path(__file__).resolve().parent.parent)
    if filled:
        print(f".env : secrets locaux générés pour {', '.join(filled)}.")
    else:
        print(".env : tous les secrets locaux sont déjà présents.")


if __name__ == "__main__":
    sys.exit(main())
