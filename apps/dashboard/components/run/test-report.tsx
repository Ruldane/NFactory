import { cn } from "cn";

import { TONE_CLASSES } from "@/components/runs/tone";
import type { CheckResult, JUnitReport, RunStep } from "@/lib/api/types";
import { describeStepState } from "@/lib/run-state";

const VERIFYING = new Set(["checks", "tests"]);

function checksOf(steps: RunStep[]): CheckResult[] {
  return steps
    .filter((s) => VERIFYING.has(s.name))
    .flatMap((s) => (Array.isArray(s.output.checks) ? (s.output.checks as CheckResult[]) : []));
}

function reportOf(steps: RunStep[]): JUnitReport | null {
  const tests = steps.find((s) => s.name === "tests");
  return (tests?.output.report as JUnitReport | undefined) ?? null;
}

// What the runner measured (JUnit report and exit codes), not what an agent claimed.
export function TestReport({ steps }: { steps: RunStep[] }) {
  const checks = checksOf(steps);
  const report = reportOf(steps);
  if (checks.length === 0 && report === null) {
    return (
      <p className="border border-dashed border-navy/25 px-6 py-8 text-center text-sm text-navy/70">
        Aucune vérification exécutée pour l&apos;instant.
      </p>
    );
  }
  return (
    <div className="space-y-6">
      {report ? (
        <div
          role="group"
          aria-label="Résultat des tests"
          className={cn("flex flex-wrap items-baseline gap-x-6 gap-y-1 border px-5 py-4", TONE_CLASSES[report.ok ? "success" : "danger"])}
        >
          <span className="font-display text-3xl">
            {report.passed} / {report.total}
          </span>
          <span className="text-sm">
            {report.ok ? "tests réussis (rapport pytest)" : "tests réussis : la suite est en échec"}
          </span>
          {report.skipped > 0 ? (
            <span className="font-mono text-xs">{report.skipped} ignoré(s)</span>
          ) : null}
        </div>
      ) : null}
      {report && report.failures.length > 0 ? (
        <ul aria-label="Tests en échec" className="space-y-2">
          {report.failures.map((failure) => (
            <li key={failure.name} className="border-l-2 border-coral-deep pl-3">
              <p className="font-mono text-sm text-navy">{failure.name}</p>
              <p className="font-mono text-xs whitespace-pre-wrap text-coral-deep">{failure.message}</p>
            </li>
          ))}
        </ul>
      ) : null}
      <ul aria-label="Vérifications" className="divide-y divide-navy/10 border-y border-navy/10">
        {checks.map((check, index) => {
          const { glyph, label } = describeStepState(check.ok ? "SUCCEEDED" : "FAILED");
          return (
            <li key={`${check.name}-${index}`} className="flex items-center gap-3 py-2.5 text-sm">
              <span aria-hidden className="font-mono">
                {glyph}
              </span>
              <span className="text-navy">{check.name}</span>
              <span className="ml-auto font-mono text-[11px] uppercase tracking-wider text-navy/60">
                {label}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
