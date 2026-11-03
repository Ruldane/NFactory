// Display metadata for coding-agent tasks and their sandbox checks (tasks 4.3, 4.4):
// glyph + French label, never color alone.

import type { AgentEvent } from "@/lib/api/types";
import type { StateDescription } from "@/lib/run-state";

const STATUS: Record<string, StateDescription> = {
  preparing: { label: "Préparation", tone: "active", glyph: "◔" },
  running: { label: "En cours", tone: "active", glyph: "▶" },
  awaiting_user: { label: "En attente de vous", tone: "attention", glyph: "◐" },
  succeeded: { label: "Terminée avec des changements", tone: "success", glyph: "✓" },
  no_changes: { label: "Terminée sans changement", tone: "attention", glyph: "∅" },
  failed: { label: "Échouée", tone: "danger", glyph: "✗" },
  cancelled: { label: "Annulée", tone: "neutral", glyph: "■" },
  discarded: { label: "Abandonnée", tone: "neutral", glyph: "○" },
};

export const describeTaskStatus = (status: string): StateDescription =>
  STATUS[status] ?? { label: status, tone: "neutral", glyph: "·" };

export const isTaskActive = (status: string) => status === "preparing" || status === "running";

// A change can be tested once it is on the bridge's side: imported, or left by the agent.
export const isTaskCheckable = (status: string) => status === "succeeded" || status === "no_changes";

const CHECK_STATUS: Record<string, StateDescription> = {
  queued: { label: "En file", tone: "active", glyph: "◔" },
  running: { label: "Tests en cours", tone: "active", glyph: "▶" },
  passed: { label: "Tests réussis", tone: "success", glyph: "✓" },
  failed: { label: "Tests en échec", tone: "danger", glyph: "✗" },
  not_tested: { label: "Non testé", tone: "attention", glyph: "∅" },
  error: { label: "Test impossible", tone: "danger", glyph: "!" },
};

export const describeCheckStatus = (status: string): StateDescription =>
  CHECK_STATUS[status] ?? { label: status, tone: "neutral", glyph: "·" };

export const isCheckActive = (status: string) => status === "queued" || status === "running";

export const CHANGE_LABELS: Record<string, string> = {
  added: "ajouté",
  modified: "modifié",
  deleted: "supprimé",
};

export interface EventLine {
  glyph: string;
  label: string;
  text: string;
  detail?: string;
}

const count = new Intl.NumberFormat("fr-FR");

// A command shows up twice, when it starts and when it ends: keep only the end once known.
export function visibleEvents(events: AgentEvent[]): AgentEvent[] {
  return events.filter((event, index) => {
    const started = event.type === "command" && (event.exit_code === undefined || event.exit_code === null);
    const next = events[index + 1];
    return !(started && next?.type === "command" && next.command === event.command);
  });
}

export function describeAgentEvent(event: AgentEvent): EventLine {
  switch (event.type) {
    case "started":
      return { glyph: "▶", label: "Démarrage", text: "L'agent a ouvert sa session." };
    case "message":
      return { glyph: "✎", label: "Agent", text: event.text ?? "" };
    case "command": {
      const done = event.exit_code !== undefined && event.exit_code !== null;
      const glyph = !done ? "…" : event.exit_code === 0 ? "✓" : "✗";
      return {
        glyph,
        label: "Commande",
        text: event.command ?? "",
        ...(done ? { detail: `code ${event.exit_code}` } : {}),
      };
    }
    case "file_change":
      return {
        glyph: "±",
        label: "Fichiers",
        text: (event.changes ?? []).map((change) => change.path).join(", "),
      };
    case "completed": {
      const read = event.usage?.input_tokens;
      const written = event.usage?.output_tokens;
      const detail =
        read !== undefined && written !== undefined
          ? `${count.format(read)} jetons lus · ${count.format(written)} écrits`
          : undefined;
      return { glyph: "■", label: "Fin", text: "L'agent a terminé.", ...(detail ? { detail } : {}) };
    }
    case "warning":
      return { glyph: "!", label: "Avertissement", text: event.message ?? "" };
    default:
      return { glyph: "✗", label: "Erreur", text: event.message ?? "" };
  }
}
