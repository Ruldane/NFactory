// Live Factory helpers: which run to follow, and how to filter its event log.

import type { RecentRun, RunEvent } from "@/lib/api/types";
import { isTerminalRunState } from "@/lib/run-state";

export type EventFilter = "all" | "agents" | "checks" | "steps" | "errors";

export const EVENT_FILTERS: { key: EventFilter; label: string }[] = [
  { key: "all", label: "Tout" },
  { key: "agents", label: "Agents" },
  { key: "checks", label: "Vérifications et tests" },
  { key: "steps", label: "Étapes" },
  { key: "errors", label: "Erreurs" },
];

/** The run the user chose if it is listed, else one still in progress, else the newest. */
export function pickRun(recent: RecentRun[], chosen: string | null): string | null {
  if (chosen && recent.some((run) => run.id === chosen)) return chosen;
  return (recent.find((run) => !isTerminalRunState(run.state)) ?? recent[0])?.id ?? null;
}

function category(event: RunEvent): Exclude<EventFilter, "all" | "errors"> {
  if (event.type.startsWith("agent.") || event.type === "repair.started") return "agents";
  if (event.type.startsWith("tool.") || event.type.startsWith("test.")) return "checks";
  return "steps";
}

export function isErrorEvent(event: RunEvent): boolean {
  if (event.type.endsWith(".failed")) return true;
  return event.type === "tool.invoked" && event.payload.exit_code !== 0;
}

export function filterEvents(events: RunEvent[], filter: EventFilter): RunEvent[] {
  if (filter === "all") return events;
  if (filter === "errors") return events.filter(isErrorEvent);
  return events.filter((event) => category(event) === filter);
}

export function repairAttempts(events: RunEvent[]): number {
  return events.filter((event) => event.type === "repair.started").length;
}
