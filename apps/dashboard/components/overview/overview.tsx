"use client";

import { useState } from "react";

import { CallTable } from "@/components/overview/call-table";
import { DemoBadge } from "@/components/overview/demo-badge";
import { FactoryMetricsSection } from "@/components/overview/factory-metrics";
import { Kpi } from "@/components/overview/kpi";
import { RecentRuns } from "@/components/overview/recent-runs";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboardSummary, useRecipes } from "@/lib/api/queries";
import type { DashboardSummary, OverviewFilters } from "@/lib/api/types";
import { formatCost, formatDuration, formatPercent } from "@/lib/format";
import { PERIODS } from "@/lib/metrics";

const SELECT = "border border-navy/25 bg-cream px-3 py-1.5 text-sm text-navy";

function Filters({
  value,
  onChange,
}: {
  value: OverviewFilters;
  onChange: (next: OverviewFilters) => void;
}) {
  const recipes = useRecipes();
  const types = [
    ...new Map(
      (recipes.data?.items ?? []).map((r) => [r.project_type, r.label]),
    ).entries(),
  ];
  return (
    <div
      role="group"
      aria-label="Filtres"
      className="flex flex-wrap items-end gap-4"
    >
      <label className="space-y-1 text-sm">
        <span className="block font-mono text-[11px] uppercase tracking-[0.14em] text-navy/60">
          Période
        </span>
        <select
          className={SELECT}
          value={value.days === null ? "" : String(value.days)}
          onChange={(event) =>
            onChange({
              ...value,
              days: event.target.value ? Number(event.target.value) : null,
            })
          }
        >
          {PERIODS.map((period) => (
            <option key={period.value} value={period.value}>
              {period.label}
            </option>
          ))}
        </select>
      </label>
      <label className="space-y-1 text-sm">
        <span className="block font-mono text-[11px] uppercase tracking-[0.14em] text-navy/60">
          Type de projet
        </span>
        <select
          className={SELECT}
          value={value.project_type ?? ""}
          onChange={(event) =>
            onChange({ ...value, project_type: event.target.value || null })
          }
        >
          <option value="">Tous les types</option>
          {types.map(([type, label]) => (
            <option key={type} value={type}>
              {label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

export function Overview() {
  const [filters, setFilters] = useState<OverviewFilters>({
    days: null,
    project_type: null,
  });
  const { data, error, isPending } = useDashboardSummary(filters);

  return (
    <div className="space-y-12">
      <header className="flex flex-wrap items-end justify-between gap-4 nf-rise">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-coral-deep">
            Vue d&apos;ensemble
          </p>
          <h1 className="mt-2 font-display text-5xl text-navy md:text-6xl">
            L&apos;usine,{" "}
            <em className="text-coral-deep">en un coup d&apos;œil</em>
          </h1>
        </div>
        {data?.demo_data ? <DemoBadge /> : null}
      </header>

      <Filters value={filters} onChange={setFilters} />

      {error ? (
        <div
          role="alert"
          className="border-l-4 border-coral-deep bg-coral-deep/8 px-5 py-4 text-sm text-navy"
        >
          <p className="font-semibold">
            Impossible de charger les indicateurs.
          </p>
          <p className="mt-1">{error.message}</p>
        </div>
      ) : isPending ? (
        <OverviewSkeleton />
      ) : (
        <OverviewContent summary={data} />
      )}
    </div>
  );
}

function OverviewContent({ summary }: { summary: DashboardSummary }) {
  const { runs } = summary;
  return (
    <>
      <section
        aria-label="Indicateurs"
        className="grid grid-cols-2 gap-x-6 gap-y-8 md:grid-cols-3 xl:grid-cols-6 nf-rise [animation-delay:80ms]"
      >
        <Kpi label="Projets" value={String(summary.projects)} />
        <Kpi
          label="Runs actifs"
          value={String(runs.active)}
          hint={`${runs.total} au total`}
        />
        <Kpi
          label="Taux de réussite"
          value={formatPercent(summary.success_rate)}
          hint={`${runs.completed} réussis · ${runs.failed} en échec`}
        />
        <Kpi
          label="Durée moyenne"
          value={formatDuration(summary.avg_duration_seconds)}
        />
        <Kpi
          label="Coût estimé"
          value={formatCost(summary.cost_estimate_usd)}
        />
        <Kpi
          label="Validations en attente"
          value={String(summary.approvals_pending)}
          highlight={summary.approvals_pending > 0}
          hint={
            summary.approvals_pending > 0
              ? "Décision humaine requise"
              : undefined
          }
        />
      </section>

      <section
        aria-labelledby="recent-runs-title"
        className="nf-rise [animation-delay:160ms]"
      >
        <div className="mb-4 flex items-baseline justify-between">
          <h2
            id="recent-runs-title"
            className="font-display text-2xl text-navy"
          >
            Derniers runs
          </h2>
          <p className="font-mono text-[11px] uppercase tracking-wider text-navy/55">
            Chaque case = une étape de fabrication
          </p>
        </div>
        <RecentRuns runs={summary.recent_runs} />
      </section>

      <FactoryMetricsSection metrics={summary.metrics} />

      <section aria-labelledby="engines-title" className="space-y-4">
        <h2 id="engines-title" className="font-display text-2xl text-navy">
          Moteurs et agents
        </h2>
        <CallTable
          label="Moteurs et modèles"
          rows={summary.providers}
          rowKey={(row) => `${row.provider}/${row.model}`}
          columns={[
            { title: "Moteur", cell: (row) => row.provider },
            { title: "Modèle", cell: (row) => row.model },
          ]}
        />
        <CallTable
          label="Agents"
          rows={summary.agents}
          rowKey={(row) => row.agent}
          columns={[{ title: "Agent", cell: (row) => row.agent }]}
        />
      </section>
    </>
  );
}

function OverviewSkeleton() {
  return (
    <div
      aria-busy="true"
      aria-label="Chargement des indicateurs"
      className="space-y-10"
    >
      <div className="grid grid-cols-2 gap-6 md:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-24 bg-navy/8" />
        ))}
      </div>
      <Skeleton className="h-48 bg-navy/8" />
    </div>
  );
}
