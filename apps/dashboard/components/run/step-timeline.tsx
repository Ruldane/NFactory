import { cn } from "cn";

import { TONE_CLASSES } from "@/components/runs/tone";
import { agentLabel } from "@/lib/agents";
import type { RunStep } from "@/lib/api/types";
import { formatDuration, formatStepName } from "@/lib/format";
import { describeStepState } from "@/lib/run-state";

import { RepairList, repairsOf } from "./repair-list";

const skipReason = (step: RunStep): string | null =>
  typeof step.output?.skipped === "string" ? step.output.skipped : null;

function seconds(step: RunStep): number | null {
  if (!step.started_at || !step.ended_at) return null;
  return (Date.parse(step.ended_at) - Date.parse(step.started_at)) / 1000;
}

// The production line, vertical: each station with its agent, state, retries and error.
export function StepTimeline({ steps }: { steps: RunStep[] }) {
  return (
    <ol aria-label="Étapes du run" className="relative space-y-1">
      <span aria-hidden className="absolute top-3 bottom-3 left-[13px] w-px bg-navy/15" />
      {steps.map((step) => {
        const { tone, glyph, label } = describeStepState(step.state);
        const duration = seconds(step);
        return (
          <li key={step.id} className="relative grid grid-cols-[28px_minmax(0,1fr)] gap-3 py-1.5">
            <span
              aria-hidden
              className={cn(
                "z-10 grid size-7 place-items-center rounded-[3px] border bg-cream font-mono text-xs",
                TONE_CLASSES[tone],
                tone === "active" && "motion-safe:animate-pulse",
              )}
            >
              {glyph}
            </span>
            <div className="min-w-0">
              <p className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-medium text-navy">{formatStepName(step.name)}</span>
                <span className="font-mono text-[11px] uppercase tracking-wider text-navy/60">
                  {label}
                </span>
                {step.attempts > 1 ? (
                  <span className="font-mono text-[11px] text-eggplant">
                    {step.attempts} tentatives
                  </span>
                ) : null}
                {duration !== null ? (
                  <span className="ml-auto font-mono text-[11px] text-navy/45">
                    {formatDuration(duration)}
                  </span>
                ) : null}
              </p>
              <p className="font-mono text-[10px] uppercase tracking-wider text-navy/45">
                {agentLabel(step.agent_role)}
              </p>
              {skipReason(step) ? (
                <p className="mt-0.5 text-xs text-navy/60">{skipReason(step)}</p>
              ) : null}
              <RepairList repairs={repairsOf(step)} />
              {step.error ? (
                <p className="mt-1 border-l-2 border-coral-deep pl-2 text-xs whitespace-pre-wrap text-coral-deep">
                  {step.error}
                </p>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
