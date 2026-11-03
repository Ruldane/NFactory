import { Kpi } from "@/components/overview/kpi";
import type { FactoryMetrics } from "@/lib/api/types";
import { FACTORY_METRICS } from "@/lib/metrics";

// The metrics of spec §14.1, then where each one comes from.
export function FactoryMetricsSection({
  metrics,
}: {
  metrics: FactoryMetrics;
}) {
  return (
    <section aria-label="Qualité de l'usine" className="space-y-6">
      <h2 className="font-display text-2xl text-navy">
        Qualité de l&apos;usine
      </h2>
      <div className="grid grid-cols-2 gap-x-6 gap-y-8 md:grid-cols-4">
        {FACTORY_METRICS.map((metric) => {
          const value = metrics[metric.key];
          return (
            <Kpi
              key={metric.key}
              label={metric.label}
              value={metric.format(value)}
              highlight={Boolean(metric.alertWhenAboveZero && value)}
            />
          );
        })}
      </div>
      <details className="text-sm text-navy/80">
        <summary className="cursor-pointer font-mono text-[11px] uppercase tracking-[0.14em] text-navy/60">
          D&apos;où viennent ces chiffres
        </summary>
        <dl className="mt-3 grid gap-x-6 gap-y-2 md:grid-cols-[14rem_1fr]">
          {FACTORY_METRICS.map((metric) => (
            <div key={metric.key} className="contents">
              <dt className="font-medium text-navy">{metric.label}</dt>
              <dd>{metric.source}</dd>
            </div>
          ))}
        </dl>
      </details>
    </section>
  );
}
