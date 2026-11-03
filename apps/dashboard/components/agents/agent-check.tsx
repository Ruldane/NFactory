"use client";

// The sandbox test of an agent's change (task 4.4). NFactory copies the task's files from
// the bridge and runs the tests in its sandbox; the verdict comes from the JUnit report.

import { cn } from "cn";
import { useState } from "react";

import { TONE_CLASSES } from "@/components/runs/tone";
import { ALERT, KICKER, SECONDARY } from "@/components/ui/form-styles";
import { useAgentCheck, useStartCheck } from "@/lib/api/agent-tasks";
import type { AgentCheck } from "@/lib/api/types";
import { describeCheckStatus, isCheckActive } from "@/lib/agent-task-status";

function CheckTag({ status }: { status: string }) {
  const state = describeCheckStatus(status);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 font-mono text-[11px] font-medium uppercase tracking-wider",
        TONE_CLASSES[state.tone],
      )}
    >
      <span aria-hidden>{state.glyph}</span>
      {state.label}
    </span>
  );
}

function Verdict({ check }: { check: AgentCheck }) {
  const report = check.report;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <CheckTag status={check.status} />
        {report ? (
          <span className="font-mono text-sm text-navy">
            {report.passed} réussi{report.passed > 1 ? "s" : ""} · {report.failed + report.errors} en échec
          </span>
        ) : null}
      </div>
      {check.error ? <p className="text-sm text-navy/80">{check.error}</p> : null}
      {report?.failures.length ? (
        <ul aria-label="Tests en échec" className="space-y-1 text-sm">
          {report.failures.map((failure) => (
            <li key={failure.name}>
              <span className="font-mono text-coral-deep">{failure.name}</span>
              {failure.message ? <span className="ml-2 text-navy/70">{failure.message}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {report?.output_tail ? (
        <details className="text-sm">
          <summary className="cursor-pointer text-navy/70">Sortie de {report.command}</summary>
          <pre className="mt-2 max-h-64 overflow-auto bg-navy/6 p-3 font-mono text-[12px] whitespace-pre-wrap [font-variant-ligatures:none]">
            {report.output_tail}
          </pre>
        </details>
      ) : null}
    </div>
  );
}

function CheckResult({ id, pollMs }: { id: string; pollMs: number }) {
  const check = useAgentCheck(id, pollMs);
  if (check.error) return <div role="alert" className={ALERT}>{check.error.message}</div>;
  if (!check.data || isCheckActive(check.data.status)) {
    return <CheckTag status={check.data?.status ?? "queued"} />;
  }
  return <Verdict check={check.data} />;
}

export function AgentCheckPanel({ taskId, pollMs }: { taskId: string; pollMs: number }) {
  const start = useStartCheck();
  const [checkId, setCheckId] = useState<string | null>(null);
  return (
    <section aria-label="Test dans le sandbox" className="space-y-3 border border-navy/15 bg-cream/60 p-5">
      <h3 className={KICKER}>Test dans le sandbox</h3>
      <p className="text-sm text-navy/70">
        NFactory copie les fichiers de la tâche et lance pytest dans son sandbox, sans réseau, jamais sur
        votre poste. Les dépendances du dépôt ne sont pas installées.
      </p>
      <button
        type="button"
        className={SECONDARY}
        disabled={start.isPending}
        onClick={() => start.mutate(taskId, { onSuccess: (check) => setCheckId(check.id) })}
      >
        {checkId ? "Relancer le test" : "Tester dans le sandbox"}
      </button>
      {start.error ? <div role="alert" className={ALERT}>{start.error.message}</div> : null}
      {checkId ? <CheckResult key={checkId} id={checkId} pollMs={pollMs} /> : null}
    </section>
  );
}
