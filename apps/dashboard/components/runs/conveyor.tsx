import { cn } from "cn";

import { TONE_CLASSES } from "@/components/runs/tone";
import type { StepBrief } from "@/lib/api/types";
import { formatStepName } from "@/lib/format";
import { describeStepState } from "@/lib/run-state";

// A run drawn as a production line: one station per pipeline step, joined by a rail.
// Every station carries a glyph and a spoken label, so color is never the only signal.

function stationLabel(step: StepBrief): string {
  const { label } = describeStepState(step.state);
  const retries = step.attempts > 1 ? ` (${step.attempts} tentatives)` : "";
  return `${formatStepName(step.name)} : ${label}${retries}`;
}

export function Conveyor({ steps }: { steps: StepBrief[] }) {
  return (
    <ol aria-label="Étapes du run" className="relative flex items-center gap-1.5">
      {/* The rail behind the stations */}
      <span aria-hidden className="absolute inset-x-1 top-1/2 h-px -translate-y-1/2 bg-navy/15" />
      {steps.map((step) => {
        const { tone, glyph } = describeStepState(step.state);
        const label = stationLabel(step);
        return (
          <li
            key={step.name}
            aria-label={label}
            title={label}
            className={cn(
              "relative grid size-6 place-items-center rounded-[3px] border font-mono text-[11px] leading-none",
              TONE_CLASSES[tone],
              tone === "active" && "motion-safe:animate-pulse",
            )}
          >
            <span aria-hidden>{glyph}</span>
            {step.attempts > 1 ? (
              <span
                aria-hidden
                className="absolute -top-1.5 -right-1.5 rounded-full bg-eggplant px-1 font-mono text-[9px] text-cream"
              >
                {step.attempts}
              </span>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
