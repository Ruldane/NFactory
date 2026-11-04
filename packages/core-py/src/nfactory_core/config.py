"""NFactory settings, read from the environment (see .env.example)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    nfactory_env: Literal["development", "test", "production"] = "development"
    nfactory_mode: Literal["local", "team", "enterprise"] = "local"
    nfactory_demo_mode: bool = True
    nfactory_log_level: str = "INFO"
    nfactory_default_locale: Literal["fr", "en"] = "fr"

    database_url: str = "postgresql+psycopg://nfactory:nfactory_dev_only@127.0.0.1:55432/nfactory"
    redis_url: str = "redis://127.0.0.1:56379/0"
    artifact_storage: Literal["local", "s3"] = "local"
    artifact_root: str = "./data/artifacts"
    workspace_root: str = "./data/workspaces"

    # Guardrails
    max_repair_attempts: int = Field(default=3, ge=0, le=10)
    max_agent_steps: int = Field(default=100, ge=1)
    max_llm_calls_per_run: int = Field(default=80, ge=1)
    max_concurrent_runs: int = Field(default=2, ge=1)
    default_run_timeout_seconds: int = Field(default=1800, ge=10)
    default_provider_fallback: Literal["ask_user", "none"] = "ask_user"
    allow_network_in_code_sandbox: bool = False
    allow_auto_push: bool = False
    allow_auto_merge: bool = False
    allow_privileged_execution: bool = False

    # Observability (task 5.2): spans go to this OTLP/HTTP collector when it is set.
    otel_exporter_otlp_endpoint: str | None = None

    # Providers (ADR-0006). Private hosts a custom endpoint may reach (e.g. a vLLM on
    # the LAN); everything else must be a public HTTPS address.
    nfactory_allowed_private_llm_hosts: list[str] = []
    ollama_base_url: str = "http://127.0.0.1:11434"

    # Code sandbox (ADR-0005). Empty URL = run checks as local subprocesses (dev only).
    nfactory_sandbox_url: str = ""
    nfactory_sandbox_token: SecretStr = SecretStr("")
    # Preview gateway (task 3.10), as the browser reaches it: its own origin.
    nfactory_preview_public_url: str = "http://127.0.0.1:8090"
    # Local bridge on the user's machine (task 4.1); Compose sets host.docker.internal.
    nfactory_bridge_url: str = "http://127.0.0.1:8765"

    # Secrets are never logged: SecretStr hides the value when printed.
    nfactory_session_secret: SecretStr = SecretStr("")
    nfactory_secret_key: SecretStr = SecretStr("")

    # Sign-in (ADR-0013). "local": one user, no sign-in. "oidc": every API route needs a
    # session opened through the OpenID Connect issuer (Google by default).
    nfactory_auth_mode: Literal["local", "oidc"] = "local"
    nfactory_oidc_issuer: str = "https://accounts.google.com"
    nfactory_oidc_client_id: str = ""
    nfactory_oidc_client_secret: SecretStr = SecretStr("")
    # Where the issuer sends the browser back: through the dashboard, so the cookie is its.
    nfactory_oidc_redirect_url: str = "http://127.0.0.1:3000/api/v1/auth/callback"
    # Admission is denied unless listed. Comma-separated; domains match Google's "hd".
    nfactory_oidc_allowed_domains: str = ""
    nfactory_oidc_allowed_emails: str = ""
    nfactory_oidc_owner_emails: str = ""
    nfactory_session_ttl_hours: int = Field(default=12, ge=1, le=720)
    # Who answers data-protection requests (e-mail or page), shown on the sign-in screen.
    nfactory_privacy_contact: str = Field(default="", max_length=200)

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
