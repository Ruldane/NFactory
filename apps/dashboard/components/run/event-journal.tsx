import type { RunEvent } from "@/lib/api/types";
import { describeEvent } from "@/lib/run-events";

const time = new Intl.DateTimeFormat("fr-FR", { timeStyle: "medium" });

// Newest first; announced politely to screen readers as the run progresses.
export function EventJournal({ events }: { events: RunEvent[] }) {
  return (
    <section aria-label="Journal du run" className="border border-navy/10 bg-eggplant text-cream">
      <h2 className="border-b border-cream/10 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.2em] text-cream/60">
        Journal en direct
      </h2>
      {events.length === 0 ? (
        <p className="px-4 py-6 font-mono text-xs text-cream/60">En attente d&apos;événements…</p>
      ) : (
        <ol aria-live="polite" className="max-h-[26rem] overflow-auto px-4 py-2">
          {[...events].reverse().map((event) => (
            <li key={event.seq} className="flex gap-3 py-1 font-mono text-xs">
              <span className="shrink-0 text-cream/45">{time.format(new Date(event.created_at))}</span>
              <span className={event.type.endsWith("failed") ? "text-coral" : "text-cream/90"}>
                {describeEvent(event)}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
