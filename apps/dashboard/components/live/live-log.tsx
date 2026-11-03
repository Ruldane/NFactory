"use client";

import { cn } from "cn";
import { useState } from "react";

import type { RunEvent } from "@/lib/api/types";
import {
  EVENT_FILTERS,
  type EventFilter,
  filterEvents,
  isErrorEvent,
} from "@/lib/live";
import { describeEvent } from "@/lib/run-events";

const time = new Intl.DateTimeFormat("fr-FR", { timeStyle: "medium" });

function trace(event: RunEvent): string {
  const id = event.payload.trace_id;
  return typeof id === "string" && id ? ` · trace ${id.slice(0, 8)}` : "";
}

// Filterable live log of one run, newest first.
export function LiveLog({ events }: { events: RunEvent[] }) {
  const [filter, setFilter] = useState<EventFilter>("all");
  const shown = filterEvents(events, filter);

  return (
    <section
      aria-label="Journal filtrable"
      className="border border-navy/10 bg-eggplant text-cream"
    >
      <div className="flex flex-wrap gap-2 border-b border-cream/10 px-4 py-3">
        {EVENT_FILTERS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            aria-pressed={filter === key}
            onClick={() => setFilter(key)}
            className={cn(
              "border px-3 py-1 font-mono text-[11px] transition-colors focus-visible:outline-2 focus-visible:outline-coral",
              filter === key
                ? "border-butter bg-butter text-eggplant"
                : "border-cream/25 text-cream/75 hover:border-cream/60",
            )}
          >
            {label} ({filterEvents(events, key).length})
          </button>
        ))}
      </div>
      {shown.length === 0 ? (
        <p className="px-4 py-6 font-mono text-xs text-cream/60">
          Aucun événement pour ce filtre.
        </p>
      ) : (
        <ol
          aria-live="polite"
          className="max-h-[32rem] overflow-auto px-4 py-2"
        >
          {[...shown].reverse().map((event) => (
            <li key={event.seq} className="flex gap-3 py-1 font-mono text-xs">
              <span className="shrink-0 text-cream/45">
                {time.format(new Date(event.created_at))}
              </span>
              <span
                className={isErrorEvent(event) ? "text-coral" : "text-cream/90"}
              >
                {describeEvent(event)}
                <span className="text-cream/45">{trace(event)}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
