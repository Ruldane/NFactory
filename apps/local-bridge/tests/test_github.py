"""GitHub through the user's official `gh` (task 4.6): fixed argv, draft PRs only, every
fact read back from GitHub. A fake `gh` records what would run."""

import json

import pytest

from nfactory_bridge.detection import Completed
from nfactory_bridge.github import GitHub, GitHubRefused, parse_remote


class FakeGh:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str | None]] = []
        self.answers: dict[str, Completed] = {}

    def __call__(self, argv: list[str], stdin: str | None = None) -> Completed:
        self.calls.append((argv, stdin))
        for key, answer in self.answers.items():
            if key in " ".join(argv):
                return answer
        return Completed(0, "", "")


@pytest.fixture
def gh() -> FakeGh:
    return FakeGh()


@pytest.fixture
def hub(gh: FakeGh) -> GitHub:
    return GitHub(gh=lambda: "gh", run=gh)


@pytest.mark.parametrize(
    ("url", "slug"),
    [
        ("https://github.com/Ruldane/nfactory-test.git", "Ruldane/nfactory-test"),
        ("https://github.com/Ruldane/nfactory-test", "Ruldane/nfactory-test"),
        ("git@github.com:Ruldane/nfactory-test.git", "Ruldane/nfactory-test"),
        ("ssh://git@github.com/Ruldane/nfactory-test.git", "Ruldane/nfactory-test"),
        ("https://gitlab.com/Ruldane/nfactory-test.git", None),
        ("https://github.com/Ruldane/../etc", None),
        ("C:/repos/bare.git", None),
    ],
)
def test_only_github_remotes_name_a_repository(url: str, slug: str | None) -> None:
    assert parse_remote(url) == slug


def test_a_pull_request_is_always_a_draft_with_the_body_on_stdin(hub: GitHub, gh: FakeGh) -> None:
    gh.answers["pr create"] = Completed(0, "https://github.com/Ruldane/nfactory-test/pull/1\n", "")

    hub.create_draft_pr(
        "Ruldane/nfactory-test",
        base="main",
        head="nfactory/nfactory-test/t_0123456789ab",
        title="Ajoute divide",
        body="Corps; rm -rf /",
    )

    argv, stdin = gh.calls[-1]
    assert argv[:3] == ["gh", "pr", "create"]
    assert "--draft" in argv
    assert argv[argv.index("--repo") + 1] == "Ruldane/nfactory-test"
    assert argv[argv.index("--head") + 1] == "nfactory/nfactory-test/t_0123456789ab"
    assert stdin == "Corps; rm -rf /"
    assert "Corps; rm -rf /" not in argv
    assert not any("merge" in part for call, _ in gh.calls for part in call)


def test_only_nfactory_branches_and_valid_repositories_are_used(hub: GitHub) -> None:
    with pytest.raises(GitHubRefused):
        hub.create_draft_pr("Ruldane/nfactory-test", base="main", head="main", title="t", body="")
    with pytest.raises(GitHubRefused):
        hub.branch_sha("../x", "nfactory/a/t_0123456789ab")


def test_the_pushed_commit_is_read_from_github(hub: GitHub, gh: FakeGh) -> None:
    gh.answers["git/ref/heads"] = Completed(0, json.dumps({"object": {"sha": "a" * 40}}), "")

    assert hub.branch_sha("Ruldane/nfactory-test", "nfactory/a/t_0123456789ab") == "a" * 40
    assert gh.calls[-1][0][:2] == ["gh", "api"]


def test_a_branch_missing_on_github_is_none(hub: GitHub, gh: FakeGh) -> None:
    gh.answers["git/ref/heads"] = Completed(1, "", "gh: Not Found (HTTP 404)")

    assert hub.branch_sha("Ruldane/nfactory-test", "nfactory/a/t_0123456789ab") is None


def test_the_pull_request_state_is_read_from_github(hub: GitHub, gh: FakeGh) -> None:
    pr = {
        "number": 3,
        "url": "https://github.com/Ruldane/nfactory-test/pull/3",
        "state": "MERGED",
        "isDraft": False,
        "headRefOid": "b" * 40,
        "mergedAt": "2026-11-03T08:00:00Z",
        "extra": "dropped",
    }
    gh.answers["pr list"] = Completed(0, json.dumps([pr]), "")

    found = hub.find_pr("Ruldane/nfactory-test", "nfactory/a/t_0123456789ab")

    assert found == {
        "number": 3,
        "url": "https://github.com/Ruldane/nfactory-test/pull/3",
        "state": "MERGED",
        "draft": False,
        "head": "b" * 40,
        "merged": True,
    }


def test_no_pull_request_yet_is_none(hub: GitHub, gh: FakeGh) -> None:
    gh.answers["pr list"] = Completed(0, "[]", "")

    assert hub.find_pr("Ruldane/nfactory-test", "nfactory/a/t_0123456789ab") is None


def test_a_gh_failure_is_a_refusal_without_its_output(hub: GitHub, gh: FakeGh) -> None:
    gh.answers["repos/Ruldane/nfactory-test"] = Completed(1, "", "HTTP 401 token ghp_secret")

    with pytest.raises(GitHubRefused) as refused:
        hub.default_branch("Ruldane/nfactory-test")
    assert "ghp_secret" not in str(refused.value)
