import { cn } from "cn";

import { TONE_CLASSES } from "@/components/runs/tone";
import type { RunStep, RunTrace } from "@/lib/api/types";
import { formatCost, formatDuration, formatStepName } from "@/lib/format";
import { describeStepState } from "@/lib/run-state";

// Steps after which the pipeline loops back through a repair when checks fail.
const REPAIRABLE = new Set(["checks", "tests"]);

function seconds(step: RunStep): number | null {
  if (!step.started_at || !step.ended_at) return null;
  return (Date.parse(step.ended_at) - Date.parse(step.started_at)) / 1000;
}

// The agent graph (spec §9.3 Live Factory): each station of the line with its agent,
// state, duration and attempts, plus the bounded repair loop after the checks.
function callsAndCost(
  trace: RunTrace | undefined,
  stepId: string,
): string | null {
  const span = trace?.spans.find((s) => s.kind === "step" && s.id === stepId);
  if (!span?.calls) return null;
  return `${span.calls} appel${span.calls > 1 ? "s" : ""} · ${formatCost(span.cost_usd ?? null)}`;
}

export function AgentGraph({
  steps,
  repairs,
  trace,
}: {
  steps: RunStep[];
  repairs: number;
  trace?: RunTrace;
}) {
  const lastRepairable = steps.findLast((step) =>
    REPAIRABLE.has(step.name),
  )?.name;
  return (
    <ol
      aria-label="Graphe des agents"
      className="flex flex-wrap items-stretch gap-y-4"
    >
      {steps.map((step, index) => {
        const { tone, glyph, label } = describeStepState(step.state);
        const duration = seconds(step);
        const name = formatStepName(step.name);
        const spend = callsAndCost(trace, step.id);
        return (
          <li
            key={step.id}
            aria-label={`${name} — ${label}`}
            className="flex items-center"
          >
            <div
              className={cn(
                "w-40 border bg-cream px-3 py-2.5",
                TONE_CLASSES[tone],
                tone === "active" && "motion-safe:animate-pulse",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-navy">{name}</span>
                <span aria-hidden className="font-mono text-xs">
                  {glyph}
                </span>
              </div>
              <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-navy/50">
                {step.agent_role}
              </p>
              <p className="mt-1 font-mono text-[11px] text-navy/70">
                {label}
                {duration !== null ? ` · ${formatDuration(duration)}` : ""}
                {step.attempts > 1 ? ` · ${step.attempts} tentatives` : ""}
              </p>
              {spend ? (
                <p className="font-mono text-[11px] text-navy/60">{spend}</p>
              ) : null}
            </div>
            {step.name === lastRepairable ? (
              <span className="mx-2 border border-dashed border-coral/60 px-2 py-1 font-mono text-[10px] text-coral-deep">
                ↺ correction{repairs > 0 ? ` ×${repairs}` : ""}
              </span>
            ) : null}
            {index < steps.length - 1 ? (
              <span aria-hidden className="px-2 text-navy/35">
                →
              </span>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
