// Run event log helpers: merge replayed SSE events and describe them in French.

import type { RunEvent } from "@/lib/api/types";
import { formatStepName } from "@/lib/format";
import { ROLE_LABELS } from "@/lib/provider-status";

// Mirrors EventType in packages/core-py/src/nfactory_core/events/contract.py. SSE named
// events only reach listeners registered for their exact type.
export const EVENT_TYPES = [
  "run.created",
  "run.started",
  "run.state_changed",
  "run.completed",
  "run.failed",
  "run.cancelled",
  "step.started",
  "step.completed",
  "step.failed",
  "step.skipped",
  "agent.started",
  "agent.progress",
  "tool.invoked",
  "provider.failed",
  "knowledge.retrieved",
  "approval.requested",
  "approval.resolved",
  "artifact.created",
  "test.passed",
  "test.failed",
  "repair.started",
  "repair.applied",
  "repair.abandoned",
  "security.scanned",
  "changes.computed",
] as const;

const FINAL = new Set(["run.completed", "run.failed", "run.cancelled"]);

export function isFinalEvent(event: RunEvent): boolean {
  return FINAL.has(event.type);
}

export function mergeEvents(current: RunEvent[], incoming: RunEvent[]): RunEvent[] {
  const bySeq = new Map(current.map((e) => [e.seq, e]));
  for (const event of incoming) bySeq.set(event.seq, event);
  return [...bySeq.values()].sort((a, b) => a.seq - b.seq);
}

const text = (value: unknown): string => (value === undefined || value === null ? "" : String(value));

type Describer = (p: Record<string, unknown>) => string;

const DESCRIBERS: Record<string, Describer> = {
  "run.created": () => "Run créé, en file d'attente",
  "run.started": (p) => (p.resumed ? "Run repris après interruption" : "Run démarré"),
  "run.state_changed": (p) => {
    if (p.requested_by === "user") return "Annulation demandée";
    if (p.resumed) return "Run repris après interruption";
    return `État : ${text(p.state)}`;
  },
  "run.completed": () => "Run terminé",
  "run.failed": (p) => `Run en échec : ${text(p.error)}`,
  "run.cancelled": () => "Run annulé",
  "step.started": (p) => `${formatStepName(text(p.step))} : démarrage`,
  "step.completed": (p) => `${formatStepName(text(p.step))} : terminé`,
  "step.failed": (p) => `${formatStepName(text(p.step))} : échec`,
  "step.skipped": (p) => `${formatStepName(text(p.step))} : non exécuté (${text(p.reason)})`,
  "agent.progress": (p) =>
    `Agent ${text(p.agent)}${p.model ? ` (${text(p.model)})` : ""} a répondu`,
  "tool.invoked": (p) =>
    `${text(p.check)} : ${p.exit_code === 0 ? "réussi" : `code de sortie ${text(p.exit_code)}`}`,
  "test.passed": (p) => `Tests réussis : ${text(p.passed)} / ${text(p.total)}`,
  "test.failed": (p) => `Tests en échec : ${text(p.passed)} / ${text(p.total)} réussis`,
  "repair.started": (p) => `Correction automatique, tentative ${text(p.attempt)}`,
  "repair.applied": (p) => {
    const count = Array.isArray(p.files) ? p.files.length : 0;
    const files = `${count} fichier${count > 1 ? "s" : ""}`;
    return `Correction ${text(p.attempt)} appliquée (${files}) : ${text(p.cause)}`;
  },
  "repair.abandoned": (p) => `Correction abandonnée : ${text(p.reason)}`,
  "security.scanned": (p) => {
    const found = Number(p.findings ?? 0);
    if (found === 0) return `Recherche de secrets : aucun secret dans ${text(p.files)} fichiers`;
    return `Recherche de secrets : ${found} secret${found > 1 ? "s" : ""} probable${found > 1 ? "s" : ""} (valeurs masquées)`;
  },
  "changes.computed": (p) => {
    const count = (n: unknown, word: string) => {
      const value = Number(n ?? 0);
      return `${value} ${word}${value > 1 ? "s" : ""}`;
    };
    return `Modifications depuis ${text(p.parent_run_id)} : ${count(p.added, "ajouté")}, ${count(p.modified, "modifié")}, ${count(p.removed, "supprimé")}`;
  },
  "artifact.created": (p) => `Livrable enregistré : ${text(p.filename)}`,
  "provider.failed": (p) =>
    `Moteur en échec (${ROLE_LABELS[text(p.role)] ?? text(p.role)}) : ${text(p.message)}`,
  "knowledge.retrieved": (p) => {
    const count = Array.isArray(p.sources) ? p.sources.length : 0;
    if (p.error) return `Base de connaissances : ${text(p.error)}`;
    if (count === 0) return "Base de connaissances : aucune source pertinente";
    return `Base de connaissances : ${count} source${count > 1 ? "s" : ""} retrouvée${count > 1 ? "s" : ""}`;
  },
  "approval.requested": () => "Run en pause : votre décision est attendue",
  "approval.resolved": (p) =>
    p.decision === "approved"
      ? `Décision : reprise avec ${text(p.provider)} · ${text(p.model)}`
      : "Décision : run arrêté",
};

export function describeEvent(event: RunEvent): string {
  const describe = DESCRIBERS[event.type];
  return describe ? describe(event.payload) : event.type;
}
