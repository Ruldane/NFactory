"""Secret scan (A10, spec §8.3 and §19.1): deterministic, and it never repeats a value.

Fake secrets are assembled at run time, so no secret-looking literal sits in the repo.
"""

import pytest

from nfactory_worker.brief import Brief
from nfactory_worker.recipes import get_recipe
from nfactory_worker.recipes.registry import registered_kinds
from nfactory_worker.security import Finding, scan_files

AWS = "AKIA" + "Q" * 16
GITHUB = "ghp_" + "a1B2" * 9
OPENAI = "sk-" + "proj-" + "x7Y" * 10
ANTHROPIC = "sk-ant-" + "api03-" + "Zz9" * 12
PRIVATE_KEY = "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----"


@pytest.mark.parametrize(
    ("content", "rule"),
    [
        (f"key = '{AWS}'\n", "aws-access-key"),
        (f"TOKEN={GITHUB}\n", "github-token"),
        (f"client = OpenAI(api_key='{OPENAI}')\n", "api-key"),
        (f"ANTHROPIC = '{ANTHROPIC}'\n", "api-key"),
        (f"{PRIVATE_KEY}\n", "private-key"),
        ("password = 'Sup3rS3cret!x'\n", "assigned-secret"),
        ('{"client_secret": "a8f5f167f44f4964e6c998dee827110c"}\n', "assigned-secret"),
    ],
)
def test_secrets_are_found_with_file_line_and_rule(content: str, rule: str) -> None:
    findings = scan_files({"src/config.py": "# config\n" + content})

    assert [(f.path, f.line, f.rule) for f in findings] == [("src/config.py", 2, rule)]


@pytest.mark.parametrize(
    "content",
    [
        "password = ''\n",
        "password = '<votre-mot-de-passe>'\n",
        "api_key = os.environ['OPENAI_API_KEY']\n",
        "token = '${GITHUB_TOKEN}'\n",
        "secret = 'changeme'\n",
        "password = 'xxxxxxxxxxxx'\n",
        "DATABASE_URL=postgresql+psycopg://<utilisateur>:<secret>@<hôte>:5432/<base>\n",
        "NOT_FOUND = 'Élément introuvable'\n",
        "def test_wrong_token_is_rejected(): assert check(token='nope') is False\n",
    ],
)
def test_placeholders_and_references_are_not_secrets(content: str) -> None:
    assert scan_files({"app/settings.py": content}) == []


def test_a_finding_never_carries_the_value() -> None:
    (finding,) = scan_files({"a.txt": f"cle = {AWS}\n"})

    assert AWS not in repr(finding) and AWS not in finding.message
    assert "a.txt:1" in finding.message


def test_a_filled_env_file_is_reported_but_an_example_is_not() -> None:
    files = {".env": "DEBUG=1\nAPI_TOKEN=abc123def456ghi\n", ".env.example": "API_TOKEN=\n"}

    rules = {(f.path, f.rule) for f in scan_files(files)}

    assert rules == {(".env", "env-file")}


def test_binary_and_huge_files_are_skipped() -> None:
    files: dict[str, str | bytes] = {
        "logo.png": b"\x89PNG\x00" + AWS.encode(),
        "big.txt": "x" * 2_000_001 + AWS,
    }

    assert scan_files(files) == []


def test_findings_are_sorted_and_typed() -> None:
    findings = scan_files({"b.py": f"k = '{AWS}'\n", "a.py": f"t = '{GITHUB}'\n"})

    assert [f.path for f in findings] == ["a.py", "b.py"]
    assert all(isinstance(f, Finding) for f in findings)


@pytest.mark.parametrize("kind", sorted(registered_kinds()))
def test_no_recipe_output_looks_like_a_secret(kind: str) -> None:
    brief = Brief(title="Gestion des licences", summary="Suivre les licences.", project_type="api")

    assert scan_files(get_recipe(kind).render(brief).files) == []
