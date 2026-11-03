// Display metadata for run and step states. Each state has a glyph so meaning never
// depends on color alone (WCAG, spec §9.1).

export type Tone = "success" | "danger" | "attention" | "active" | "neutral";

export interface StateDescription {
  label: string;
  tone: Tone;
  glyph: string;
}

const RUN_STATES: Record<string, StateDescription> = {
  DRAFT: { label: "Brouillon", tone: "neutral", glyph: "○" },
  PLANNING: { label: "Planification", tone: "active", glyph: "◔" },
  WAITING_FOR_INPUT: { label: "Question en attente", tone: "attention", glyph: "?" },
  APPROVAL_PENDING: { label: "Validation requise", tone: "attention", glyph: "!" },
  QUEUED: { label: "En file", tone: "neutral", glyph: "…" },
  RUNNING: { label: "En cours", tone: "active", glyph: "▸" },
  REVIEW_PENDING: { label: "Prêt pour revue", tone: "attention", glyph: "◎" },
  COMPLETED: { label: "Terminé", tone: "success", glyph: "✓" },
  PARTIAL: { label: "Partiel", tone: "attention", glyph: "◐" },
  FAILED: { label: "Échec", tone: "danger", glyph: "✕" },
  CANCELLED: { label: "Annulé", tone: "neutral", glyph: "⊘" },
};

const STEP_STATES: Record<string, StateDescription> = {
  PENDING: { label: "À venir", tone: "neutral", glyph: "○" },
  RUNNING: { label: "En cours", tone: "active", glyph: "▸" },
  SUCCEEDED: { label: "Réussi", tone: "success", glyph: "✓" },
  FAILED: { label: "Échec", tone: "danger", glyph: "✕" },
  SKIPPED: { label: "Non exécuté", tone: "neutral", glyph: "–" },
  CANCELLED: { label: "Annulé", tone: "neutral", glyph: "⊘" },
};

const unknown = (state: string): StateDescription => ({ label: state, tone: "neutral", glyph: "·" });

export function describeRunState(state: string): StateDescription {
  return RUN_STATES[state] ?? unknown(state);
}

export function describeStepState(state: string): StateDescription {
  return STEP_STATES[state] ?? unknown(state);
}

const TERMINAL_RUN_STATES = new Set(["COMPLETED", "PARTIAL", "FAILED", "CANCELLED"]);

export function isTerminalRunState(state: string): boolean {
  return TERMINAL_RUN_STATES.has(state);
}
