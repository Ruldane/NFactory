"""Pairing: a one-time code shown in the user's terminal becomes a long-lived token.
Only the token's hash is kept on disk."""

import json
from pathlib import Path

import pytest

from nfactory_bridge.pairing import Pairing, PairingRefused


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_the_code_gives_a_token_once(tmp_path: Path) -> None:
    pairing = Pairing(tmp_path / "bridge.json", clock=Clock())
    code = pairing.new_code()

    token = pairing.pair(code)

    assert len(token) >= 40
    assert pairing.authorized(token)
    with pytest.raises(PairingRefused):
        pairing.pair(code)  # single use


def test_only_the_hash_of_the_token_is_stored(tmp_path: Path) -> None:
    store = tmp_path / "bridge.json"
    pairing = Pairing(store, clock=Clock())
    token = pairing.pair(pairing.new_code())

    saved = store.read_text(encoding="utf-8")

    assert token not in saved
    assert set(json.loads(saved)) == {"token_sha256"}


def test_the_pairing_survives_a_restart(tmp_path: Path) -> None:
    first = Pairing(tmp_path / "bridge.json", clock=Clock())
    token = first.pair(first.new_code())

    again = Pairing(tmp_path / "bridge.json", clock=Clock())

    assert again.paired and again.authorized(token)
    assert not again.authorized("x" * len(token))


def test_a_wrong_or_missing_token_is_refused(tmp_path: Path) -> None:
    pairing = Pairing(tmp_path / "bridge.json", clock=Clock())
    assert not pairing.authorized("anything")  # nothing paired yet
    pairing.pair(pairing.new_code())
    assert not pairing.authorized("")
    assert not pairing.authorized("wrong")


def test_the_code_expires(tmp_path: Path) -> None:
    clock = Clock()
    pairing = Pairing(tmp_path / "bridge.json", clock=clock, code_ttl_s=600)
    code = pairing.new_code()
    clock.now += 601

    with pytest.raises(PairingRefused):
        pairing.pair(code)


def test_too_many_wrong_codes_burn_the_code(tmp_path: Path) -> None:
    pairing = Pairing(tmp_path / "bridge.json", clock=Clock(), max_attempts=3)
    code = pairing.new_code()
    for _ in range(3):
        with pytest.raises(PairingRefused):
            pairing.pair("WRONG-CODE")

    with pytest.raises(PairingRefused):
        pairing.pair(code)  # the right one no longer works: a new code is needed


def test_the_code_tolerates_case_and_spaces(tmp_path: Path) -> None:
    pairing = Pairing(tmp_path / "bridge.json", clock=Clock())
    code = pairing.new_code()

    assert pairing.authorized(pairing.pair(f"  {code.lower()} "))


def test_a_new_pairing_replaces_the_old_token(tmp_path: Path) -> None:
    pairing = Pairing(tmp_path / "bridge.json", clock=Clock())
    old = pairing.pair(pairing.new_code())

    new = pairing.pair(pairing.new_code())

    assert pairing.authorized(new) and not pairing.authorized(old)


def test_unpair_forgets_the_token(tmp_path: Path) -> None:
    pairing = Pairing(tmp_path / "bridge.json", clock=Clock())
    token = pairing.pair(pairing.new_code())

    pairing.unpair()

    assert not pairing.paired and not pairing.authorized(token)
