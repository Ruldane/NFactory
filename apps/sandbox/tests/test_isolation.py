"""Sandbox tests of spec §19.1 against real Docker: time and CPU bounded, network
blocked, files outside the run unreachable. A real supervisor container receives the
commands through the worker's own `SandboxRunner`.

Skipped (with the reason) when Docker or the sandbox image is missing.
"""

import json
import os
import secrets
import shutil
import subprocess
import time
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from nfactory_worker.runner import CommandResult, SandboxRunner

IMAGE = os.environ.get("NFACTORY_SANDBOX_IMAGE", "nfactory-sandbox:latest")


def _docker(*args: str, check: bool = True) -> str:
    done = subprocess.run(["docker", *args], capture_output=True, text=True, check=False)
    if check and done.returncode != 0:
        raise RuntimeError(f"docker {args[0]}: {done.stderr.strip()}")
    return done.stdout.strip()


def _image_has_supervisor() -> bool:
    if not shutil.which("docker"):
        return False
    probe = ["run", "--rm", "--network", "none", IMAGE, "python", "-c", "import nfactory_sandbox"]
    return subprocess.run(["docker", *probe], capture_output=True, check=False).returncode == 0


pytestmark = pytest.mark.skipif(
    not _image_has_supervisor(),
    reason=f"Docker ou l'image {IMAGE} avec le superviseur absents (docker compose build)",
)


@dataclass
class Stack:
    runner: SandboxRunner
    own: str  # the workspace the commands run in
    other: str  # another run's workspace, holding a secret
    suffix: str
    url: str
    token: str
    network: str  # the internal preview network

    async def python(self, code: str, timeout_s: int = 60) -> CommandResult:
        return await self.runner.run(self.own, ("python", "-c", code), timeout_s)


@pytest.fixture(scope="module")
def stack() -> Iterator[Stack]:
    suffix = secrets.token_hex(4)
    volume = f"nfactory-test-ws-{suffix}"
    own, other = f"run_own_{suffix}", f"run_other_{suffix}"
    token = secrets.token_urlsafe(24)
    seed = (
        f"import os; os.makedirs('/data/workspaces/{own}'); "
        f"os.makedirs('/data/workspaces/{other}'); "
        f"open('/data/workspaces/{other}/secret.txt', 'w').write('confidentiel')"
    )
    seed += (
        f"; open('/data/workspaces/{own}/probe_app.py', 'w', encoding='utf-8').write({PROBE_APP!r})"
    )
    network = f"nfactory-test-preview-{suffix}"
    _docker("volume", "create", volume)
    _docker("network", "create", "--internal", network)
    supervisor = f"nfactory-test-supervisor-{suffix}"
    try:
        _docker("run", "--rm", "-v", f"{volume}:/data/workspaces", IMAGE, "python", "-c", seed)
        _docker(
            "run", "-d", "--name", supervisor,
            "-v", "/var/run/docker.sock:/var/run/docker.sock",
            "-v", f"{volume}:/data/workspaces:ro",
            "--group-add", "0", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "-e", f"NFACTORY_SANDBOX_TOKEN={token}",
            "-e", f"NFACTORY_SANDBOX_IMAGE={IMAGE}",
            "-e", f"NFACTORY_WORKSPACES_VOLUME={volume}",
            "-e", f"NFACTORY_PREVIEW_NETWORK={network}",
            "-p", "127.0.0.1::8800", "-w", "/srv",
            IMAGE, "python", "-m", "nfactory_sandbox",
        )  # fmt: skip
        port = _docker("port", supervisor, "8800/tcp").splitlines()[0].rsplit(":", 1)[1]
        url = f"http://127.0.0.1:{port}"
        _wait_healthy(url, supervisor)
        yield Stack(SandboxRunner(url, token), own, other, suffix, url, token, network)
    finally:
        _docker("rm", "-f", supervisor, check=False)
        _docker("rm", "-f", f"nfactory-preview-{own}", check=False)
        _docker("network", "rm", network, check=False)
        for leftover in _docker(
            "ps", "-aq", "--filter", f"label=nfactory.workspace={own}", check=False
        ).split():
            _docker("rm", "-f", leftover, check=False)
        _docker("volume", "rm", "-f", volume, check=False)


# A stand-in for a generated app: on GET it reports what it can reach from inside.
PROBE_APP = """import json, os, pathlib, socket
from http.server import BaseHTTPRequestHandler, HTTPServer

def probe(host, port):
    try:
        socket.create_connection((host, port), timeout=3).close()
        return "open"
    except OSError:
        return "blocked"

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            pathlib.Path("written.txt").write_text("x")
            write = "possible"
        except OSError:
            write = "refused"
        other = [p.name for p in pathlib.Path("..").iterdir()]
        seen = {"internet": probe("1.1.1.1", 443), "write": write, "siblings": other}
        body = json.dumps(seen).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

HTTPServer(("0.0.0.0", int(os.environ["PORT"])), H).serve_forever()
"""


def _wait_healthy(url: str, supervisor: str) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"supervisor not healthy: {_docker('logs', supervisor, check=False)}")


async def test_the_network_is_blocked(stack: Stack) -> None:
    code = (
        "import socket\n"
        "for target in (('1.1.1.1', 53), ('host.docker.internal', 80)):\n"
        "    try:\n"
        "        socket.create_connection(target, 3)\n"
        "        print('OUVERT', target)\n"
        "    except OSError as exc:\n"
        "        print('bloqué', type(exc).__name__)\n"
    )
    result = await stack.python(code)

    assert result.exit_code == 0, result.stderr
    assert "OUVERT" not in result.stdout
    assert result.stdout.count("bloqué") == 2


async def test_another_runs_files_are_unreachable(stack: Stack) -> None:
    code = (
        "import os, json; print(json.dumps({"
        "'listing': os.listdir('/data/workspaces'), "
        f"'secret': os.path.exists('/data/workspaces/{stack.other}/secret.txt')"
        "}))"
    )
    result = await stack.python(code)

    seen = json.loads(result.stdout)
    assert seen == {"listing": [stack.own], "secret": False}


async def test_only_the_workspace_and_tmp_are_writable(stack: Stack) -> None:
    code = (
        "import pathlib\n"
        "pathlib.Path('livrable.txt').write_text('ok')\n"
        "pathlib.Path('/tmp/scratch').write_text('ok')\n"
        "for target in ('/etc/nfactory', '/srv/x', '/data/workspaces/x'):\n"
        "    try:\n"
        "        pathlib.Path(target).write_text('x')\n"
        "        print('ÉCRIT', target)\n"
        "    except OSError:\n"
        "        print('refusé')\n"
    )
    result = await stack.python(code)
    again = await stack.python("print(open('livrable.txt').read())")

    assert result.exit_code == 0, result.stderr
    assert "ÉCRIT" not in result.stdout and result.stdout.count("refusé") == 3
    assert again.stdout.strip() == "ok"  # the workspace persists across commands


async def test_a_command_past_its_timeout_is_stopped(stack: Stack) -> None:
    started = time.monotonic()
    result = await stack.python("import time; time.sleep(60)", timeout_s=2)

    assert result.timed_out is True
    assert time.monotonic() - started < 20


async def test_cpu_memory_and_processes_are_capped(stack: Stack) -> None:
    code = (
        "import json, pathlib\n"
        "cg = pathlib.Path('/sys/fs/cgroup')\n"
        "print(json.dumps({name: (cg / name).read_text().strip()"
        " for name in ('cpu.max', 'memory.max', 'pids.max')}))\n"
    )
    result = await stack.python(code)

    assert json.loads(result.stdout) == {
        "cpu.max": "100000 100000",  # one CPU
        "memory.max": str(1024**3),
        "pids.max": "256",
    }


async def test_exceeding_the_memory_is_killed_and_explained(stack: Stack) -> None:
    result = await stack.python("blocks = [bytearray(64 * 1024**2) for _ in range(40)]")

    assert result.exit_code == 137
    assert "Mémoire dépassée" in result.stderr


async def test_no_privilege_and_no_secret_reach_the_command(stack: Stack) -> None:
    # GPG_KEY, set by the Python base image, is the public release-signing fingerprint.
    code = (
        "WORDS = ('TOKEN', 'SECRET', 'PASSWORD', 'API_KEY', 'NFACTORY_SANDBOX')\n"
        "import os, json\n"
        "status = dict(line.split(':\\t', 1) for line in open('/proc/self/status')"
        " if ':\\t' in line)\n"
        "print(json.dumps({'uid': os.getuid(), 'caps': status['CapEff'].strip(),"
        " 'secret': [k for k in os.environ if any(w in k for w in WORDS)]}))\n"
    )
    result = await stack.python(code)

    assert json.loads(result.stdout) == {"uid": 10001, "caps": "0000000000000000", "secret": []}


async def test_no_container_is_left_behind(stack: Stack) -> None:
    await stack.python("print('fin')")

    left = _docker("ps", "-aq", "--filter", f"label=nfactory.workspace={stack.own}")
    assert left == ""


def _supervisor(stack: Stack, method: str, path: str, body: object = None) -> dict:  # type: ignore[type-arg]
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(stack.url + path, data=data, method=method)
    request.add_header("Authorization", f"Bearer {stack.token}")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())  # type: ignore[no-any-return]


def test_a_preview_is_confined_and_reachable_only_on_its_network(stack: Stack) -> None:
    started = _supervisor(
        stack, "POST", "/previews", {"workspace": stack.own, "argv": ["python", "probe_app.py"]}
    )
    host = started["host"]
    fetch = (
        "import time, urllib.request\n"
        "for _ in range(40):\n"
        "    try:\n"
        f"        print(urllib.request.urlopen('http://{host}:8000/', timeout=3).read().decode())\n"
        "        break\n"
        "    except OSError: time.sleep(0.5)\n"
    )
    try:
        seen = json.loads(
            _docker("run", "--rm", "--network", stack.network, IMAGE, "python", "-c", fetch)
        )
        # The generated app has no Internet, cannot change its workspace, sees no other run.
        assert seen == {"internet": "blocked", "write": "refused", "siblings": seen["siblings"]}
        assert stack.other not in seen["siblings"]
        assert _supervisor(stack, "GET", f"/previews/{stack.own}")["running"] is True
        # From the host, nothing is published.
        assert _docker("port", host, check=False) == ""
    finally:
        _supervisor(stack, "DELETE", f"/previews/{stack.own}")
    assert _docker("ps", "-aq", "--filter", f"name={host}") == ""
