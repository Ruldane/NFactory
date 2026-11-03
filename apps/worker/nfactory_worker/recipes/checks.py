"""Standard checks shared by Python-based recipes."""

from nfactory_worker.recipes.base import Check

JUNIT_PATH = ".nfactory/junit.xml"


def ruff_check() -> Check:
    return Check(
        name="Analyse statique (ruff)",
        stage="static",
        argv=("python", "-m", "ruff", "check", "--no-cache", "."),
        timeout_s=60,
    )


def pytest_check() -> Check:
    return Check(
        name="Tests (pytest)",
        stage="tests",
        argv=(
            "python",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--rootdir=.",
            f"--junitxml={JUNIT_PATH}",
        ),
        timeout_s=300,
        junit_path=JUNIT_PATH,
    )


def python_script(path: str, name: str) -> Check:
    return Check(name=name, stage="build", argv=("python", path), timeout_s=120)
