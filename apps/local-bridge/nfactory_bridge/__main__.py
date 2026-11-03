"""Run the bridge on the user's machine (outside Docker): scripts/bridge.ps1 or
scripts/bridge.sh, which run `python -m nfactory_bridge` from apps/local-bridge.

Options: --port (default 8765), --store (pairing file), --pair (show a new pairing code).
The pairing file holds a token hash only; it lives in the user's profile, out of the repo.
"""

import argparse
import os
import sys
from collections.abc import Callable
from http.server import ThreadingHTTPServer
from pathlib import Path

from nfactory_bridge import __version__
from nfactory_bridge.detection import detect
from nfactory_bridge.pairing import CODE_TTL_S, Pairing
from nfactory_bridge.server import make_server

DEFAULT_PORT = 8765
HOST = "127.0.0.1"


def default_store() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.join(Path.home(), ".config")
    return Path(base) / "NFactory" / "bridge.json"


def start(argv: list[str], say: Callable[[str], None]) -> tuple[ThreadingHTTPServer, Pairing]:
    parser = argparse.ArgumentParser(prog="nfactory-bridge", description="Pont local NFactory")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--store", type=Path, default=default_store())
    parser.add_argument("--pair", action="store_true", help="afficher un nouveau code")
    args = parser.parse_args(argv)
    pairing = Pairing(args.store)
    server = make_server(HOST, args.port, pairing=pairing, detect=detect)
    port = server.server_address[1]
    say(f"Pont local NFactory {__version__} : http://{HOST}:{port} (boucle locale uniquement)")
    if args.pair or not pairing.paired:
        code = pairing.new_code()
        minutes = CODE_TTL_S // 60
        say(f"Code d'appairage : {code} (valable {minutes} min, à saisir dans NFactory)")
        say("Dans NFactory : page Moteurs IA, section Outils locaux, Associer le pont.")
    else:
        say("Déjà associé à NFactory. Relancez avec --pair pour un nouveau code.")
    return server, pairing


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        # A console that cannot show a character must not stop the bridge.
        sys.stdout.reconfigure(errors="replace")
    server, _ = start(sys.argv[1:], lambda line: print(line, flush=True))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Pont arrêté.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
