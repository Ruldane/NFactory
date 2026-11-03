// Display metadata for provider connection states (spec §6). Glyph + French label, so
// meaning never depends on color alone. Only a successful test gives "Connecté".

import type { StateDescription } from "@/lib/run-state";
import { AGENTS } from "@/lib/agents";

const STATUSES: Record<string, StateDescription> = {
  not_configured: { label: "Non configuré", tone: "neutral", glyph: "○" },
  configured: { label: "À tester", tone: "attention", glyph: "◔" },
  missing_key: { label: "Clé manquante", tone: "attention", glyph: "!" },
  connected: { label: "Connecté", tone: "success", glyph: "✓" },
  invalid_credentials: { label: "Clé refusée", tone: "danger", glyph: "✕" },
  quota_exceeded: { label: "Quota épuisé", tone: "danger", glyph: "✕" },
  rate_limited: { label: "Limite de débit", tone: "attention", glyph: "◐" },
  unreachable: { label: "Injoignable", tone: "danger", glyph: "✕" },
  blocked: { label: "Adresse refusée", tone: "danger", glyph: "⊘" },
  needs_model: { label: "Modèle requis", tone: "attention", glyph: "?" },
  error: { label: "Erreur", tone: "danger", glyph: "✕" },
};

export function describeProviderStatus(status: string): StateDescription {
  return STATUSES[status] ?? { label: status, tone: "neutral", glyph: "·" };
}

// Agent roles that call a model, as the API names them (nfactory_core.routing.ROLES).
export const ROLE_LABELS: Record<string, string> = Object.fromEntries(
  Object.entries(AGENTS)
    .filter(([, agent]) => agent.kind === "model")
    .map(([role, agent]) => [role, agent.label]),
);
