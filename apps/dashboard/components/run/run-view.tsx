"use client";

import { cn } from "cn";
import Link from "next/link";
import { type ReactNode, useState } from "react";

import { SaveRecipe } from "@/components/recipes/save-recipe";
import { ApprovalBanner } from "@/components/run/approval-banner";
import { ArtifactList } from "@/components/run/artifact-list";
import { ChangeRequest } from "@/components/run/change-request";
import { ChangesPanel, changesOf } from "@/components/run/changes-panel";
import { EventJournal } from "@/components/run/event-journal";
import { Explanation } from "@/components/run/explanation";
import { FileBrowser } from "@/components/run/file-browser";
import { PreviewPanel, hasPreview } from "@/components/run/preview-panel";
import { Sources } from "@/components/run/sources";
import { StepTimeline } from "@/components/run/step-timeline";
import { TestReport } from "@/components/run/test-report";
import { StateBadge } from "@/components/runs/state-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useCancelRun, useRun, useRunArtifacts } from "@/lib/api/queries";
import type { RunDetail } from "@/lib/api/types";
import { useRunEvents } from "@/lib/api/use-run-events";
import { formatCost, formatDateTime } from "@/lib/format";
import { isTerminalRunState } from "@/lib/run-state";

const TABS = [
  "Livrables",
  "Modifications",
  "Aperçu",
  "Tests",
  "Fichiers",
  "Explication",
  "Sources",
] as const;
type Tab = (typeof TABS)[number];

export function RunView({ runId }: { runId: string }) {
  const run = useRun(runId);
  const events = useRunEvents(runId);

  if (run.error) {
    return (
      <div
        role="alert"
        className="border-l-4 border-coral-deep bg-coral-deep/8 px-5 py-4 text-sm"
      >
        {run.error.message}
      </div>
    );
  }
  if (run.isPending)
    return (
      <Skeleton className="h-96 bg-navy/8" aria-label="Chargement du run" />
    );
  return <RunPage run={run.data} events={<EventJournal events={events} />} />;
}

// "openai_api · model-x, ollama_local · llama" : each distinct engine once.
function engineSummary(run: RunDetail): string {
  const names = [
    ...new Set(
      Object.values(run.engines ?? {}).map((e) => `${e.provider} · ${e.model}`),
    ),
  ];
  return names.length ? ` · moteurs ${names.join(", ")}` : "";
}

function RunPage({ run, events }: { run: RunDetail; events: ReactNode }) {
  const cancel = useCancelRun(run.id);
  const artifacts = useRunArtifacts(run.id);
  const [tab, setTab] = useState<Tab>("Livrables");
  const finished = isTerminalRunState(run.state);

  return (
    <div className="space-y-10">
      <header className="nf-rise space-y-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-coral-deep">
          Run · {run.id}
        </p>
        <div className="flex flex-wrap items-center gap-4">
          <h1 className="font-display text-5xl text-navy">
            {run.project.title}
          </h1>
          <StateBadge state={run.state} />
          {run.model === "demo" ? (
            <span className="rounded-sm bg-butter px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase text-eggplant">
              Modèle démo · sans IA réelle
            </span>
          ) : null}
          {finished ? null : (
            <button
              type="button"
              onClick={() => cancel.mutate()}
              disabled={cancel.isPending}
              className="ml-auto border border-coral-deep px-4 py-2 text-sm text-coral-deep transition-colors hover:bg-coral-deep hover:text-cream focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-coral-deep disabled:opacity-50"
            >
              Annuler le run
            </button>
          )}
        </div>
        {run.parent_run_id ? (
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-eggplant">
            Évolution du run{" "}
            <Link
              href={`/runs/${run.parent_run_id}`}
              className="underline underline-offset-2"
            >
              {run.parent_run_id}
            </Link>
          </p>
        ) : null}
        <blockquote className="max-w-3xl border-l-4 border-coral pl-4 text-lg text-navy/80 italic">
          {run.request}
        </blockquote>
        <p className="font-mono text-[11px] text-navy/55">
          Créé le {formatDateTime(run.created_at)}
          {run.recipe ? ` · recette ${run.recipe}` : ""}
          {run.model === "demo" ? "" : engineSummary(run)} · coût{" "}
          {formatCost(run.cost_estimate_usd)}
          {run.budget.max_llm_calls
            ? ` · ${run.budget.max_llm_calls} appels IA max`
            : ""}
          {run.trace_id ? ` · trace ${run.trace_id.slice(0, 8)}` : ""}
        </p>
        {run.state === "FAILED" && run.error ? (
          <div
            role="alert"
            className="border-l-4 border-coral-deep bg-coral-deep/8 px-5 py-4 text-sm whitespace-pre-wrap"
          >
            {run.error}
          </div>
        ) : null}
        {run.pending_approval ? (
          <ApprovalBanner run={run} approval={run.pending_approval} />
        ) : null}
        {cancel.error ? (
          <div
            role="alert"
            className="border-l-4 border-coral-deep bg-coral-deep/8 px-5 py-4 text-sm"
          >
            {cancel.error.message}
          </div>
        ) : null}
      </header>

      <div className="nf-rise grid gap-8 [animation-delay:80ms] lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <section aria-label="Chaîne de fabrication">
          <h2 className="mb-3 font-mono text-[11px] uppercase tracking-[0.2em] text-navy/60">
            Chaîne de fabrication
          </h2>
          <StepTimeline steps={run.steps} />
        </section>
        {events}
      </div>

      <section className="nf-rise [animation-delay:160ms]">
        <div
          role="tablist"
          aria-label="Résultats du run"
          className="mb-5 flex flex-wrap gap-2"
        >
          {TABS.filter(
            (name) =>
              (name !== "Aperçu" || hasPreview(run)) &&
              (name !== "Modifications" || changesOf(run) !== null),
          ).map((name) => (
            <button
              key={name}
              type="button"
              role="tab"
              aria-selected={tab === name}
              onClick={() => setTab(name)}
              className={cn(
                "rounded-sm border px-3 py-1 font-mono text-[11px] uppercase tracking-wider transition-colors",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-coral-deep",
                tab === name
                  ? "border-eggplant bg-eggplant text-cream"
                  : "border-navy/20 text-navy/75 hover:border-navy/50",
              )}
            >
              {name}
            </button>
          ))}
        </div>
        <div role="tabpanel" aria-label={tab}>
          {tab === "Livrables" ? (
            artifacts.error ? (
              <p role="alert" className="text-sm text-coral-deep">
                {artifacts.error.message}
              </p>
            ) : (
              <ArtifactList artifacts={artifacts.data?.items ?? []} />
            )
          ) : tab === "Modifications" ? (
            <ChangesPanel run={run} artifacts={artifacts.data?.items ?? []} />
          ) : tab === "Aperçu" ? (
            <PreviewPanel runId={run.id} />
          ) : tab === "Tests" ? (
            <TestReport steps={run.steps} />
          ) : tab === "Fichiers" ? (
            <FileBrowser runId={run.id} />
          ) : tab === "Explication" ? (
            <Explanation run={run} />
          ) : (
            <Sources run={run} />
          )}
        </div>
      </section>
      {run.state === "COMPLETED" ? (
        <>
          <ChangeRequest run={run} />
          <SaveRecipe run={run} />
        </>
      ) : null}
    </div>
  );
}
