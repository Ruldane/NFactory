"use client";

import Link from "next/link";
import { useState } from "react";

import { AgentGraph } from "@/components/live/agent-graph";
import { LiveLog } from "@/components/live/live-log";
import { RunTraceView } from "@/components/live/run-trace";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboardSummary, useRun, useRunTrace } from "@/lib/api/queries";
import { useRunEvents } from "@/lib/api/use-run-events";
import { pickRun, repairAttempts } from "@/lib/live";
import { describeRunState, isTerminalRunState } from "@/lib/run-state";

function Alert({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="border-l-4 border-coral-deep bg-coral-deep/8 px-5 py-4 text-sm"
    >
      {message}
    </div>
  );
}

// One run, followed live. Mounted with key={runId} so its event log starts afresh.
function FollowedRun({ runId }: { runId: string }) {
  const run = useRun(runId);
  const events = useRunEvents(runId);
  const trace = useRunTrace(
    runId,
    run.data ? !isTerminalRunState(run.data.state) : true,
  );

  if (run.error) return <Alert message={run.error.message} />;
  if (!run.data)
    return (
      <Skeleton className="h-40 bg-navy/8" aria-label="Chargement du run" />
    );

  // Only real repairs count: a step retried after a worker restart is not one.
  const repairs = repairAttempts(events);
  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <h2 className="font-display text-3xl text-navy">
          {run.data.project.title}
        </h2>
        <Link
          href={`/runs/${run.data.id}`}
          className="text-sm text-coral-deep underline underline-offset-4"
        >
          Ouvrir le run complet
        </Link>
      </div>
      <AgentGraph steps={run.data.steps} repairs={repairs} trace={trace.data} />
      {trace.data ? <RunTraceView trace={trace.data} /> : null}
      <LiveLog events={events} />
    </div>
  );
}

export function LiveFactory() {
  const summary = useDashboardSummary();
  const [chosen, setChosen] = useState<string | null>(null);

  if (summary.error) return <Alert message={summary.error.message} />;
  if (!summary.data) {
    return (
      <Skeleton className="h-64 bg-navy/8" aria-label="Chargement des runs" />
    );
  }

  const recent = summary.data.recent_runs;
  const runId = pickRun(recent, chosen);
  if (!runId) {
    return (
      <div className="border border-dashed border-navy/25 px-6 py-10 text-center text-navy/70">
        <p>Aucun run pour l&apos;instant : l&apos;usine est à l&apos;arrêt.</p>
        <Link
          href="/new"
          className="mt-3 inline-block text-coral-deep underline underline-offset-4"
        >
          Lancer un projet
        </Link>
      </div>
    );
  }

  return (
    <div className="grid gap-10 lg:grid-cols-[16rem_minmax(0,1fr)]">
      <fieldset className="space-y-2">
        <legend className="mb-3 font-mono text-[11px] uppercase tracking-[0.2em] text-navy/60">
          Run suivi
        </legend>
        {recent.map((run) => {
          const state = describeRunState(run.state);
          return (
            <label
              key={run.id}
              className="flex cursor-pointer items-center gap-3 border border-navy/15 px-3 py-2 has-[:checked]:border-eggplant has-[:checked]:bg-eggplant/5"
            >
              <input
                type="radio"
                name="followed-run"
                value={run.id}
                checked={run.id === runId}
                onChange={() => setChosen(run.id)}
                className="accent-eggplant"
              />
              <span className="min-w-0">
                <span className="block truncate text-navy">
                  {run.project_title}
                </span>
                <span className="font-mono text-[11px] text-navy/60">
                  {state.glyph} {state.label}
                </span>
              </span>
            </label>
          );
        })}
      </fieldset>
      <FollowedRun key={runId} runId={runId} />
    </div>
  );
}
