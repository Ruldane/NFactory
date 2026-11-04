"""Where each engine processes the data it receives (legal review §2, ADR-0016).

Every endpoint NFactory knows has an entry here, with the provider's own page as its
source. A fact the provider does not document stays "unknown": the "EU or local only"
policy then refuses that engine rather than guessing.

Interface: `Zone`, `Residency`, `residency`.
"""

from dataclasses import dataclass
from typing import Literal

from nfactory_core.providers.specs import SPECS

Zone = Literal["local", "eu", "outside_eu", "unknown"]


@dataclass(frozen=True)
class Residency:
    zone: Zone
    country: str  # French, shown in Moteurs IA
    source: str = ""  # the provider page that states it
    note: str = ""  # a condition the user must meet, in French


_LOCAL = Residency("local", "Votre machine ou votre réseau")
_UNKNOWN = Residency("unknown", "Non documenté")

# Sources read on 2026-11-04.
_OPENAI = "https://developers.openai.com/api/docs/guides/your-data"
_ANTHROPIC = "https://platform.claude.com/docs/en/manage-claude/data-residency"
_DEEPSEEK = "https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html"
_ZAI = "https://docs.z.ai/legal-agreement/privacy-policy"
_ZHIPU = "https://docs.bigmodel.cn/cn/terms/privacy-policy"
_KIMI = "https://platform.kimi.ai/docs/agreement/userprivacy.md"
_KIMI_CN = "https://platform.kimi.com/docs/agreement/userprivacy"
_QWEN = "https://www.alibabacloud.com/help/en/model-studio/regions"
_QWEN_EU = "https://www.alibabacloud.com/help/en/model-studio/germany-frankfurt-global"
_QWEN_SG = "https://www.alibabacloud.com/help/en/model-studio/singapore-regional-access-information"
_MINIMAX = "https://platform.minimax.io/protocol/privacy-policy"
_MINIMAX_CN = "https://platform.minimax.cn/protocol/privacy-policy"
_CODEX = "https://developers.openai.com/codex/llms-full.txt"
_CLAUDE_CODE = "https://code.claude.com/docs/en/data-usage"


def _outside(country: str, source: str, note: str = "") -> Residency:
    return Residency("outside_eu", country, source, note)


_SINGAPORE_INFERENCE = "Calcul possible sur tous les nœuds hors Chine continentale."

# (kind, region id) -> residency; region None is the kind's only endpoint.
_RESIDENCY: dict[tuple[str, str | None], Residency] = {
    ("openai_api", "global"): _outside("États-Unis", _OPENAI),
    ("openai_api", "eu"): Residency(
        "eu",
        "Union européenne",
        _OPENAI,
        "Seulement avec un projet OpenAI créé avec la résidence « Europe ». Le calcul reste "
        "dans l'UE avec la conservation zéro ou un contrôle approuvé par OpenAI.",
    ),
    ("anthropic_api", "global"): _outside(
        "États-Unis",
        _ANTHROPIC,
        "Stockage aux États-Unis ; calcul dans tout pays disponible. Aucune option UE.",
    ),
    ("deepseek_api", "global"): _outside("Chine", _DEEPSEEK),
    ("zai_glm_api", "intl"): _outside("Singapour", _ZAI),
    ("zai_glm_api", "intl-coding"): _outside("Singapour", _ZAI),
    ("zai_glm_api", "cn"): _outside("Chine", _ZHIPU),
    ("zai_glm_api", "cn-coding"): _outside("Chine", _ZHIPU),
    ("moonshot_kimi_api", "intl"): _outside("Singapour", _KIMI),
    ("moonshot_kimi_api", "cn"): _outside("Chine", _KIMI_CN),
    ("qwen_api", "cn-beijing"): _outside("Chine", _QWEN),
    ("qwen_api", "ap-southeast-1"): _outside("Singapour", _QWEN_SG, _SINGAPORE_INFERENCE),
    ("qwen_api", "us-east-1"): _outside("États-Unis", _QWEN),
    ("qwen_api", "eu-central-1"): Residency(
        "eu",
        "Allemagne",
        _QWEN_EU,
        "Seulement si l'espace Model Studio a la portée « UE ». La portée « Global » peut "
        "calculer partout, Chine continentale comprise.",
    ),
    ("qwen_api", "ap-northeast-1"): _outside("Japon", _QWEN),
    ("qwen_api", "cn-hongkong"): _outside("Hong Kong (Chine)", _QWEN),
    ("qwen_api", "legacy-intl"): _outside("Singapour", _QWEN_SG, _SINGAPORE_INFERENCE),
    ("qwen_api", "legacy-cn"): _outside("Chine", _QWEN),
    ("minimax_api", "intl"): _outside("États-Unis", _MINIMAX),
    ("minimax_api", "cn"): _outside("Chine", _MINIMAX_CN),
    ("custom_openai_compatible", None): _UNKNOWN,
    ("ollama_local", None): _LOCAL,
    ("codex_local", None): _outside(
        "États-Unis", _CODEX, "Codex tourne chez vous mais envoie le code à l'API OpenAI."
    ),
    ("claude_code_local", None): _outside(
        "États-Unis", _CLAUDE_CODE, "Claude Code tourne chez vous mais envoie le code à Anthropic."
    ),
}


def residency(kind: str, region_id: str | None = None) -> Residency:
    """The residency of an endpoint; the kind's first region when none is chosen."""
    spec = SPECS.get(kind)
    if spec is not None and spec.regions and region_id is None:
        region_id = spec.regions[0].id
    return _RESIDENCY.get((kind, region_id), _UNKNOWN)
