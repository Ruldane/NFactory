"""SSRF guard for user-typed base URLs (task 2.5): negative cases first."""

import pytest

from nfactory_core.providers.ssrf import UnsafeUrlError, UrlPolicy, check_url

CUSTOM = UrlPolicy()
OLLAMA = UrlPolicy(allow_http=True, allow_private=True)


def resolver(mapping: dict[str, list[str]]):  # type: ignore[no-untyped-def]
    return lambda host: mapping[host]


PUBLIC = resolver({"llm.example.com": ["93.184.216.34"]})


@pytest.mark.parametrize(
    ("url", "ips"),
    [
        ("https://internal.corp/v1", ["10.0.0.5"]),
        ("https://localhost/v1", ["127.0.0.1"]),
        ("https://router.lan/v1", ["192.168.1.1"]),
        ("https://v6.local/v1", ["::1"]),
        ("https://metadata.cloud/v1", ["169.254.169.254"]),
        ("https://unspecified/v1", ["0.0.0.0"]),
        ("https://mixed.example/v1", ["93.184.216.34", "10.1.2.3"]),  # one bad answer is enough
    ],
)
def test_custom_endpoint_refuses_non_public_addresses(url: str, ips: list[str]) -> None:
    host = url.split("/")[2]
    with pytest.raises(UnsafeUrlError):
        check_url(url, policy=CUSTOM, resolver=resolver({host: ips}))


@pytest.mark.parametrize(
    "url",
    [
        "http://llm.example.com/v1",  # clear text
        "ftp://llm.example.com/v1",
        "https://user:pass@llm.example.com/v1",  # credentials in the URL
        "https:///v1",
        "llm.example.com/v1",
    ],
)
def test_custom_endpoint_refuses_malformed_or_clear_text_urls(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        check_url(url, policy=CUSTOM, resolver=PUBLIC)


def test_public_https_endpoint_is_accepted() -> None:
    check_url("https://llm.example.com/v1", policy=CUSTOM, resolver=PUBLIC)


def test_unresolvable_host_is_refused() -> None:
    def fail(host: str) -> list[str]:
        raise OSError("no such host")

    with pytest.raises(UnsafeUrlError):
        check_url("https://nowhere.example/v1", policy=CUSTOM, resolver=fail)


def test_an_allow_listed_private_host_is_accepted_even_in_clear_text() -> None:
    policy = UrlPolicy(allowed_private_hosts=frozenset({"vllm.lan"}))
    check_url(
        "http://vllm.lan:8000/v1", policy=policy, resolver=resolver({"vllm.lan": ["192.168.1.20"]})
    )


def test_ollama_may_be_local_but_never_cloud_metadata() -> None:
    check_url(
        "http://127.0.0.1:11434", policy=OLLAMA, resolver=resolver({"127.0.0.1": ["127.0.0.1"]})
    )
    check_url(
        "http://host.docker.internal:11434",
        policy=OLLAMA,
        resolver=resolver({"host.docker.internal": ["192.168.65.254"]}),
    )
    with pytest.raises(UnsafeUrlError):
        check_url(
            "http://169.254.169.254/latest",
            policy=OLLAMA,
            resolver=resolver({"169.254.169.254": ["169.254.169.254"]}),
        )


def test_error_message_is_french() -> None:
    with pytest.raises(UnsafeUrlError) as caught:
        check_url(
            "https://internal.corp/v1",
            policy=CUSTOM,
            resolver=resolver({"internal.corp": ["10.0.0.5"]}),
        )
    assert "adresse" in str(caught.value).lower()
