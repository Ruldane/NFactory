"""webapp-react-fastapi recipe: the python-api backend under backend/, a React (Vite)
frontend under frontend/, Dockerfiles and a Compose file.

Brief text reaches the frontend only as data (`src/entity.json`, HTML-escaped title):
the generated JavaScript is fixed. The sandbox has no Internet, so the frontend links
the toolchain preinstalled in the image (`tools/link-frontend-deps.mjs`); its versions
are pinned here and must equal `apps/sandbox/web-deps/package.json` (tested).
"""

import html
import json

from nfactory_worker.brief import Brief, EntitySpec
from nfactory_worker.recipes.base import Check, Preview, RenderedProject
from nfactory_worker.recipes.python_api import PythonApiRecipe
from nfactory_worker.recipes.python_api.fields import DEFAULT_ENTITY
from nfactory_worker.recipes.rendering import load_template, render_template

_PACKAGE = __package__ or "nfactory_worker.recipes.webapp_react_fastapi"
BACKEND_JUNIT = ".nfactory/junit-backend.xml"
FRONTEND_JUNIT = ".nfactory/junit-frontend.xml"

FRONTEND_DEPENDENCIES = {"react": "19.3.1", "react-dom": "19.3.1"}
FRONTEND_DEV_DEPENDENCIES = {
    "@testing-library/dom": "10.4.2",
    "@testing-library/react": "16.3.3",
    "@vitejs/plugin-react": "6.1.2",
    "jsdom": "30.1.3",
    "vite": "8.3.5",
    "vitest": "5.0.5",
}
FRONTEND_VERSIONS = {**FRONTEND_DEPENDENCIES, **FRONTEND_DEV_DEPENDENCIES}
# The built frontend and the API from one process (tools/preview.py).
PREVIEW = Preview(argv=("python", "tools/preview.py"), port=8000)

# Files of the frontend copied as they are (no placeholder).
_STATIC_FRONTEND = (
    "vite.config.js",
    "src/main.jsx",
    "src/App.jsx",
    "src/ItemForm.jsx",
    "src/api.js",
    "src/fields.js",
    "src/styles.css",
    "src/App.test.jsx",
    "src/api.test.js",
    "Dockerfile",
    "nginx.conf",
    ".dockerignore",
)


class WebappRecipe:
    kind = "webapp-react-fastapi"
    version = "1.0.0"

    def render(self, brief: Brief) -> RenderedProject:
        entity = brief.entity or DEFAULT_ENTITY
        backend = PythonApiRecipe(excel_export=True).render(brief)

        def tpl(template: str, /, **values: str) -> str:
            return render_template(load_template(_PACKAGE, template), values)

        files: dict[str, str | bytes] = {
            f"backend/{path}": content for path, content in backend.files.items()
        }
        files["backend/Dockerfile"] = tpl("backend.Dockerfile")
        files["backend/.dockerignore"] = tpl("backend.dockerignore")
        files |= {f"frontend/{name}": tpl(f"frontend/{name}") for name in _STATIC_FRONTEND}
        files |= {
            "frontend/package.json": _package_json(brief),
            "frontend/index.html": tpl("frontend/index.html", title=html.escape(brief.title)),
            "frontend/src/entity.json": _entity_json(brief, entity),
            "tools/link-frontend-deps.mjs": tpl("link-frontend-deps.mjs"),
            "tools/preview.py": tpl("preview.py"),
            "compose.yaml": tpl("compose.yaml"),
            ".env.example": tpl("env.example"),
            ".gitignore": tpl("gitignore"),
            "README.md": tpl(
                "README.md",
                title=brief.title,
                summary=brief.summary or "Application générée par NFactory.",
                version=self.version,
                plural=entity.plural,
                label=entity.label,
            ),
        }
        return RenderedProject(files=files, checks=_checks(), preview=PREVIEW)


def _checks() -> tuple[Check, ...]:
    node_bin = "frontend/node_modules"
    return (
        Check(
            name="Analyse statique du backend (ruff)",
            stage="static",
            argv=("python", "-m", "ruff", "check", "--no-cache", "backend"),
            timeout_s=60,
        ),
        Check(
            name="Dépendances du frontend (hors ligne)",
            stage="build",
            argv=("node", "tools/link-frontend-deps.mjs"),
            timeout_s=60,
        ),
        Check(
            name="Construction du frontend (Vite)",
            stage="build",
            argv=("node", f"{node_bin}/vite/bin/vite.js", "build", "frontend"),
            timeout_s=300,
        ),
        Check(
            name="Tests du backend (pytest)",
            stage="tests",
            argv=(
                "python",
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "-c",
                "backend/pyproject.toml",
                "--rootdir=backend",
                f"--junitxml={BACKEND_JUNIT}",
                "backend/tests",
            ),
            timeout_s=300,
            junit_path=BACKEND_JUNIT,
        ),
        Check(
            name="Tests du frontend (Vitest)",
            stage="tests",
            argv=(
                "node",
                f"{node_bin}/vitest/vitest.mjs",
                "run",
                "--root",
                "frontend",
                "--reporter=default",
                "--reporter=junit",
                f"--outputFile.junit=../{FRONTEND_JUNIT}",
            ),
            timeout_s=300,
            junit_path=FRONTEND_JUNIT,
        ),
    )


def _package_json(brief: Brief) -> str:
    package = {
        "name": brief.slug,
        "private": True,
        "version": "0.1.0",
        "type": "module",
        "scripts": {"dev": "vite", "build": "vite build", "test": "vitest run"},
        "dependencies": FRONTEND_DEPENDENCIES,
        "devDependencies": FRONTEND_DEV_DEPENDENCIES,
    }
    return json.dumps(package, indent=2) + "\n"


def _entity_json(brief: Brief, entity: EntitySpec) -> str:
    data = {
        "title": brief.title,
        "summary": brief.summary,
        "label": entity.label,
        "plural": entity.plural,
        "fields": [{"name": f.name, "label": f.label, "type": f.type} for f in entity.fields],
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
