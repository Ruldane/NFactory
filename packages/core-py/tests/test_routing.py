"""Role routing (task 2.8): which engine answers for which agent, frozen at launch."""

import pytest

from nfactory_core.routing import (
    DEMO_MODEL_ID,
    ROLES,
    ConnectionFacts,
    Route,
    RoutingConfig,
    RoutingError,
    demo_routing,
    engines,
    freeze_routing,
    policy_violation,
)

CONNECTED = {
    "openai_api": ConnectionFacts(kind="openai_api", status="connected", local=False),
    "ollama_local": ConnectionFacts(kind="ollama_local", status="connected", local=True),
    "deepseek_api": ConnectionFacts(kind="deepseek_api", status="configured", local=False),
}


def price(provider: str, model: str) -> dict[str, float] | None:
    return {"input_per_mtok": 1.0, "output_per_mtok": 2.0} if model == "priced" else None


def test_one_default_engine_serves_every_role() -> None:
    config = RoutingConfig(default=Route(provider="openai_api", model="m1"))

    frozen = freeze_routing(config, CONNECTED, price)

    assert frozen["mode"] == "routed"
    assert set(frozen["routes"]) == set(ROLES)
    routes = frozen["routes"].values()
    assert all(r["provider"] == "openai_api" and r["model"] == "m1" for r in routes)
    assert frozen["fallback"] == "ask_user"


def test_a_role_override_wins_over_the_default_and_carries_its_price() -> None:
    config = RoutingConfig(
        default=Route(provider="openai_api", model="m1"),
        roles={"reviewer": Route(provider="ollama_local", model="priced")},
    )

    routes = freeze_routing(config, CONNECTED, price)["routes"]

    assert routes["reviewer"]["provider"] == "ollama_local"
    assert routes["reviewer"]["pricing"] == {"input_per_mtok": 1.0, "output_per_mtok": 2.0}
    assert routes["planner"]["pricing"] is None


def test_a_role_without_engine_is_refused() -> None:
    config = RoutingConfig(roles={"planner": Route(provider="openai_api", model="m1")})

    with pytest.raises(RoutingError) as caught:
        freeze_routing(config, CONNECTED, price)

    assert caught.value.code == "routing_incomplete"


def test_an_untested_provider_cannot_serve_a_run() -> None:
    config = RoutingConfig(default=Route(provider="deepseek_api", model="m"))

    with pytest.raises(RoutingError) as caught:
        freeze_routing(config, CONNECTED, price)

    assert caught.value.code == "provider_not_ready"
    assert "DeepSeek" in caught.value.message


def test_local_only_refuses_any_remote_engine() -> None:
    config = RoutingConfig(
        default=Route(provider="ollama_local", model="m"),
        roles={"planner": Route(provider="openai_api", model="m1")},
        local_only=True,
    )

    with pytest.raises(RoutingError) as caught:
        freeze_routing(config, CONNECTED, price)

    assert caught.value.code == "local_only_violation"


def test_local_only_with_local_engines_is_accepted() -> None:
    config = RoutingConfig(default=Route(provider="ollama_local", model="m"), local_only=True)

    assert freeze_routing(config, CONNECTED, price)["local_only"] is True


US = ConnectionFacts(
    kind="openai_api", status="connected", local=False, zone="outside_eu", country="États-Unis"
)
FRANKFURT = ConnectionFacts(
    kind="qwen_api", status="connected", local=False, zone="eu", country="Allemagne"
)
UNDOCUMENTED = ConnectionFacts(kind="custom_openai_compatible", status="connected", local=False)


def test_eu_only_refuses_an_engine_processing_outside_the_eu() -> None:
    config = RoutingConfig(default=Route(provider="openai_api", model="m"), eu_only=True)

    with pytest.raises(RoutingError) as caught:
        freeze_routing(config, {"openai_api": US}, price)

    assert caught.value.code == "eu_only_violation"
    assert "OpenAI" in caught.value.message and "États-Unis" in caught.value.message


def test_eu_only_refuses_an_engine_whose_country_is_not_documented() -> None:
    config = RoutingConfig(
        default=Route(provider="custom_openai_compatible", model="m"), eu_only=True
    )

    with pytest.raises(RoutingError) as caught:
        freeze_routing(config, {"custom_openai_compatible": UNDOCUMENTED}, price)

    assert caught.value.code == "eu_only_violation"
    assert "non documenté" in caught.value.message


def test_eu_only_accepts_eu_and_local_engines_and_is_frozen() -> None:
    config = RoutingConfig(
        default=Route(provider="qwen_api", model="m"),
        roles={"planner": Route(provider="ollama_local", model="m")},
        eu_only=True,
    )

    frozen = freeze_routing(config, {**CONNECTED, "qwen_api": FRANKFURT}, price)

    assert frozen["eu_only"] is True
    assert frozen["routes"]["planner"]["provider"] == "ollama_local"


def test_policy_violation_checks_one_engine() -> None:
    assert policy_violation(US, local_only=False, eu_only=False) is None
    assert policy_violation(FRANKFURT, local_only=False, eu_only=True) is None
    local = policy_violation(FRANKFURT, local_only=True, eu_only=True)
    assert local is not None and local.code == "local_only_violation"
    assert demo_routing()["eu_only"] is False


def test_empty_routing_is_not_configured() -> None:
    assert not RoutingConfig().configured
    assert RoutingConfig(default=Route(provider="openai_api", model="m")).configured


def test_unknown_role_or_provider_is_rejected_by_the_schema() -> None:
    with pytest.raises(ValueError):
        RoutingConfig(roles={"chef": Route(provider="openai_api", model="m")})
    with pytest.raises(ValueError):
        Route(provider="codex_local", model="m")  # coding agents are not chat engines
    with pytest.raises(ValueError):
        Route(provider="openai_api", model="")


def test_demo_routing_sends_every_role_to_the_demo_engine() -> None:
    frozen = demo_routing()

    assert frozen["mode"] == "demo"
    assert engines(frozen) == {role: {"provider": "demo", "model": DEMO_MODEL_ID} for role in ROLES}


def test_engines_of_a_run_launched_before_routing_existed() -> None:
    assert engines({"default": "demo"})["planner"]["provider"] == "demo"
    assert engines({}) == {}
