// Display metadata for the bridge and the local tools: glyph + French label, never color alone.

import type { StateDescription } from "@/lib/run-state";

const BRIDGE: Record<string, StateDescription> = {
  unreachable: { label: "Pont arrêté", tone: "neutral", glyph: "○" },
  unpaired: { label: "À associer", tone: "attention", glyph: "◔" },
  paired: { label: "Associé", tone: "success", glyph: "✓" },
  token_rejected: { label: "Association perdue", tone: "attention", glyph: "!" },
};

const RUNTIME: Record<string, StateDescription> = {
  not_installed: { label: "Non installé", tone: "neutral", glyph: "○" },
  installed: { label: "Statut inconnu", tone: "attention", glyph: "?" },
  needs_login: { label: "Connexion requise", tone: "attention", glyph: "!" },
  connected: { label: "Connecté", tone: "success", glyph: "✓" },
};

const fallback = (status: string): StateDescription => ({ label: status, tone: "neutral", glyph: "·" });

export const describeBridgeStatus = (status: string) => BRIDGE[status] ?? fallback(status);
export const describeRuntimeStatus = (status: string) => RUNTIME[status] ?? fallback(status);
