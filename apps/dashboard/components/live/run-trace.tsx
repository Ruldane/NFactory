import { cn } from "cn";

import type { RunTrace, TraceSpan } from "@/lib/api/types";
import { formatCost, formatLatency, formatStepName } from "@/lib/format";
import { describeSpan, spanOffsets } from "@/lib/trace";

const INDENT: Record<TraceSpan["kind"], string> = {
  run: "pl-0",
  step: "pl-4",
  agent: "pl-8",
  check: "pl-8",
};

const BAR: Record<string, string> = {
  ok: "bg-forest/70",
  error: "bg-coral-deep/80",
  running: "bg-butter motion-safe:animate-pulse",
  pending: "bg-navy/15",
  skipped: "bg-navy/15",
};

function details(span: TraceSpan): string {
  if (span.kind === "agent") {
    const engine =
      [span.provider, span.model].filter(Boolean).join(" · ") ||
      "moteur inconnu";
    const tokens =
      span.input_tokens === null && span.output_tokens === null
        ? "jetons non mesurés"
        : `${span.input_tokens ?? "—"} / ${span.output_tokens ?? "—"} jetons`;
    return `${engine} · ${tokens} · ${formatCost(span.cost_usd ?? null)}`;
  }
  if (span.kind === "check")
    return span.exit_code === null ? "" : `code ${span.exit_code}`;
  if (span.kind === "step" && span.calls)
    return `${span.calls} appel${span.calls > 1 ? "s" : ""}`;
  return "";
}

// The run's trace as a waterfall: each span's bar sits at its start within the run and
// is as wide as it lasted. Built by the API from the stored steps and events.
export function RunTraceView({ trace }: { trace: RunTrace }) {
  const offsets = spanOffsets(trace.spans);
  return (
    <section aria-labelledby="run-trace-title" className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 id="run-trace-title" className="font-display text-2xl text-navy">
          Trace du run
        </h3>
        {trace.trace_id ? (
          <p className="break-all font-mono text-[11px] text-navy/60">
            trace_id {trace.trace_id}
          </p>
        ) : null}
      </div>
      <ol aria-label="Trace du run" className="space-y-1">
        {trace.spans.map((span) => {
          const state = describeSpan(span.status);
          const name =
            span.kind === "step" ? formatStepName(span.name) : span.name;
          const place = offsets.get(span.id);
          return (
            <li
              key={span.id}
              aria-label={`${name} — ${state.label}`}
              className="grid grid-cols-[minmax(0,22rem)_minmax(0,1fr)] items-center gap-4 text-sm"
            >
              <div className={cn("min-w-0", INDENT[span.kind])}>
                <div className="flex items-baseline gap-2">
                  <span aria-hidden className="font-mono text-xs">
                    {state.glyph}
                  </span>
                  <span
                    className={cn(
                      "truncate",
                      span.kind === "run" ? "font-medium" : "",
                    )}
                  >
                    {name}
                  </span>
                  <span className="font-mono text-[11px] text-navy/60">
                    {state.label}
                    {span.duration_s !== null
                      ? ` · ${formatLatency(span.duration_s)}`
                      : ""}
                  </span>
                </div>
                {details(span) ? (
                  <p className="truncate pl-5 font-mono text-[11px] text-navy/60">
                    {details(span)}
                  </p>
                ) : null}
              </div>
              <div className="relative h-3 bg-navy/5" aria-hidden>
                {place ? (
                  <span
                    className={cn(
                      "absolute inset-y-0 min-w-[2px]",
                      BAR[span.status],
                    )}
                    style={{ left: `${place.left}%`, width: `${place.width}%` }}
                  />
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
