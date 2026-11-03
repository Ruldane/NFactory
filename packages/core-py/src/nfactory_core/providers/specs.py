"""What NFactory knows about each provider kind (spec §6.2): label, protocol, regions.

Base URLs come from the official docs (docs/research/providers.md). Model names never
appear here: they come from discovery or the admin catalog.
"""

from dataclasses import dataclass
from typing import Literal

Protocol = Literal["openai", "anthropic", "ollama", "coding_agent"]
Family = Literal["api", "local", "coding_agent"]


@dataclass(frozen=True)
class Region:
    id: str
    label: str
    # May contain `{workspace_id}` (Qwen workspace-dedicated hosts).
    base_url: str


@dataclass(frozen=True)
class ProviderSpec:
    kind: str
    label: str
    family: Family
    protocol: Protocol
    phase: int
    env_key: str | None = None
    regions: tuple[Region, ...] = ()
    # True when the user types the base URL (custom endpoint, Ollama).
    custom_url: bool = False
    # True when the provider documents a model-listing endpoint.
    discovery: bool = True
    docs_url: str = ""
    # True only when an embeddings endpoint is verified in the official docs (ADR-0007).
    embeddings: bool = False

    @property
    def needs_key(self) -> bool:
        return self.env_key is not None

    @property
    def local(self) -> bool:
        return self.family == "local"

    def region(self, region_id: str | None) -> Region | None:
        if not self.regions:
            return None
        if region_id is None:
            return self.regions[0]
        return next((r for r in self.regions if r.id == region_id), None)


def _qwen_regions() -> tuple[Region, ...]:
    host = "https://{workspace_id}.%s.maas.aliyuncs.com/compatible-mode/v1"
    regions = [
        ("cn-beijing", "Chine (Pékin)"),
        ("ap-southeast-1", "Singapour"),
        ("us-east-1", "États-Unis (Virginie)"),
        ("eu-central-1", "Allemagne (Francfort)"),
        ("ap-northeast-1", "Japon (Tokyo)"),
        ("cn-hongkong", "Chine (Hong Kong)"),
    ]
    dedicated = tuple(Region(rid, f"{label} — espace dédié", host % rid) for rid, label in regions)
    legacy = (
        Region(
            "legacy-intl",
            "Singapour — domaine DashScope historique",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        ),
        Region(
            "legacy-cn",
            "Pékin — domaine DashScope historique",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
    )
    return dedicated + legacy


SPECS: dict[str, ProviderSpec] = {
    spec.kind: spec
    for spec in (
        ProviderSpec(
            "openai_api", "OpenAI", "api", "openai", 2, "OPENAI_API_KEY",
            (Region("global", "Mondial", "https://api.openai.com/v1"),),
            docs_url="https://developers.openai.com/api/reference/overview",
            embeddings=True,
        ),
        ProviderSpec(
            "anthropic_api", "Anthropic", "api", "anthropic", 2, "ANTHROPIC_API_KEY",
            (Region("global", "Mondial", "https://api.anthropic.com"),),
            docs_url="https://platform.claude.com/docs/en/api/overview",
        ),
        ProviderSpec(
            "deepseek_api", "DeepSeek", "api", "openai", 2, "DEEPSEEK_API_KEY",
            (Region("global", "Mondial", "https://api.deepseek.com"),),
            docs_url="https://api-docs.deepseek.com/",
        ),
        ProviderSpec(
            "zai_glm_api", "Z.ai / GLM", "api", "openai", 2, "ZAI_API_KEY",
            (
                Region("intl", "International", "https://api.z.ai/api/paas/v4"),
                Region("cn", "Chine continentale", "https://open.bigmodel.cn/api/paas/v4"),
                Region("intl-coding", "International — Coding Plan", "https://api.z.ai/api/coding/paas/v4"),
                Region("cn-coding", "Chine — Coding Plan", "https://open.bigmodel.cn/api/coding/paas/v4"),
            ),
            discovery=False,
            docs_url="https://docs.z.ai/api-reference/introduction",
        ),
        ProviderSpec(
            "moonshot_kimi_api", "Moonshot / Kimi", "api", "openai", 2, "MOONSHOT_API_KEY",
            (
                Region("intl", "International", "https://api.moonshot.ai/v1"),
                Region("cn", "Chine", "https://api.moonshot.cn/v1"),
            ),
            docs_url="https://platform.kimi.ai/docs/api/chat",
        ),
        ProviderSpec(
            "qwen_api", "Alibaba Qwen", "api", "openai", 2, "DASHSCOPE_API_KEY",
            _qwen_regions(),
            discovery=False,
            docs_url="https://www.alibabacloud.com/help/en/model-studio/regions/",
        ),
        ProviderSpec(
            "minimax_api", "MiniMax", "api", "openai", 2, "MINIMAX_API_KEY",
            (
                Region("intl", "International", "https://api.minimax.io/v1"),
                Region("cn", "Chine", "https://api.minimax.cn/v1"),
            ),
            docs_url="https://platform.minimax.io/docs/api-reference/text-openai-api",
        ),
        ProviderSpec(
            "custom_openai_compatible", "Endpoint compatible OpenAI", "api", "openai", 2,
            "CUSTOM_LLM_API_KEY", custom_url=True, embeddings=True,
        ),
        ProviderSpec(
            "ollama_local", "Ollama (local)", "local", "ollama", 2, None, custom_url=True,
            docs_url="https://docs.ollama.com/api/introduction",
            embeddings=True,
        ),
        ProviderSpec("codex_local", "OpenAI Codex (local)", "coding_agent", "coding_agent", 4),
        ProviderSpec("claude_code_local", "Claude Code (local)", "coding_agent", "coding_agent", 4),
    )
}  # fmt: skip


def label(kind: str) -> str:
    spec = SPECS.get(kind)
    return spec.label if spec else kind
