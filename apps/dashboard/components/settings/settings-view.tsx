"use client";

import { type FormEvent, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { useSaveRunLimits, useWorkspaceSettings } from "@/lib/api/queries";
import type { RunLimits, WorkspaceSettings } from "@/lib/api/types";

const FIELD =
  "w-full border border-navy/20 bg-cream px-4 py-3 font-mono text-navy focus-visible:border-coral-deep focus-visible:outline-none";
const KICKER = "font-mono text-[11px] uppercase tracking-[0.2em] text-navy/60";

const LIMITS: { key: keyof RunLimits; label: string; help: string }[] = [
  {
    key: "max_llm_calls",
    label: "Appels IA par run",
    help: "Au-delà, le run s'arrête en échec « Budget dépassé ».",
  },
  {
    key: "max_agent_steps",
    label: "Étapes par run",
    help: "Limite du graphe d'agents (MAX_AGENT_STEPS).",
  },
  {
    key: "max_repair_attempts",
    label: "Tentatives de correction",
    help: "Si les tests échouent, nombre de corrections essayées avant l'échec.",
  },
];

// Not built yet: listed with the phase that brings them (spec §9.3 Settings).
const LATER: { title: string; phase: number; detail: string }[] = [
  {
    title: "Rétention et export des données",
    phase: 6,
    detail: "Durée de conservation des runs, purge et export de vos données.",
  },
];

function Environment({ settings }: { settings: WorkspaceSettings }) {
  const facts = [
    settings.mode === "local" ? "Mode local : un seul utilisateur, sur ce poste" : `Mode ${settings.mode}`,
    settings.demo_mode
      ? "Mode démo actif : les agents répondent avec un modèle de démonstration, sans IA réelle"
      : "Mode démo désactivé",
    settings.sandbox === "isolated"
      ? "Sandbox isolé, sans Internet : les tests des projets générés y sont exécutés"
      : "Sans sandbox : les tests tournent directement sur ce poste (développement uniquement)",
  ];
  return (
    <ul className="space-y-2 text-navy/80">
      {facts.map((fact) => (
        <li key={fact} className="flex gap-3">
          <span aria-hidden className="text-forest">
            ●
          </span>
          {fact}
        </li>
      ))}
    </ul>
  );
}

function LimitsForm({ settings }: { settings: WorkspaceSettings }) {
  const [values, setValues] = useState<RunLimits>(settings.run_limits);
  const save = useSaveRunLimits();

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate(values);
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <div className="grid gap-6 md:grid-cols-3">
        {LIMITS.map(({ key, label, help }) => {
          const bounds = settings.limit_bounds[key];
          return (
            <div key={key} className="space-y-2">
              <label htmlFor={`limit-${key}`} className={`block ${KICKER}`}>
                {label}
              </label>
              <input
                id={`limit-${key}`}
                aria-describedby={`limit-${key}-help`}
                type="number"
                min={bounds.min}
                max={bounds.max}
                required
                value={Number.isNaN(values[key]) ? "" : values[key]}
                onChange={(event) =>
                  setValues((current) => ({ ...current, [key]: event.target.valueAsNumber }))
                }
                className={FIELD}
              />
              <p id={`limit-${key}-help`} className="text-sm text-navy/60">
                {help} Entre {bounds.min} et {bounds.max}.
              </p>
            </div>
          );
        })}
      </div>
      {save.error ? (
        <div role="alert" className="border-l-4 border-coral-deep bg-coral-deep/8 px-5 py-4 text-sm">
          {save.error.message}
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-4">
        <button
          type="submit"
          disabled={save.isPending}
          className="bg-eggplant px-6 py-3 font-medium text-cream transition-colors hover:bg-navy focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-coral-deep disabled:cursor-not-allowed disabled:opacity-45"
        >
          Enregistrer les limites
        </button>
        {save.isSuccess ? (
          <p role="status" className="text-sm text-forest">
            ✓ Limites enregistrées. Elles s&apos;appliquent aux prochains runs.
          </p>
        ) : (
          <p className="text-sm text-navy/60">Un run garde les limites de son lancement.</p>
        )}
      </div>
    </form>
  );
}

export function SettingsView() {
  const settings = useWorkspaceSettings();

  if (settings.error) {
    return (
      <div role="alert" className="border-l-4 border-coral-deep bg-coral-deep/8 px-5 py-4 text-sm">
        {settings.error.message}
      </div>
    );
  }
  if (!settings.data) {
    return <Skeleton className="h-64 bg-navy/8" aria-label="Chargement des réglages" />;
  }

  return (
    <div className="space-y-12">
      <section className="space-y-4">
        <h2 className="font-display text-2xl text-navy">Environnement</h2>
        <Environment settings={settings.data} />
      </section>
      <section className="space-y-4">
        <h2 className="font-display text-2xl text-navy">Limites des runs</h2>
        <LimitsForm settings={settings.data} />
      </section>
      <section className="space-y-4">
        <h2 className="font-display text-2xl text-navy">À venir</h2>
        <ul className="grid gap-4 md:grid-cols-2">
          {LATER.map((item) => (
            <li
              key={item.title}
              className="border border-dashed border-navy/25 px-5 py-4 text-navy/55"
            >
              <div className="flex items-baseline justify-between gap-4">
                <span className="font-medium">{item.title}</span>
                <span className="font-mono text-[11px] uppercase tracking-[0.2em]">
                  Phase {item.phase}
                </span>
              </div>
              <p className="mt-1 text-sm">{item.detail}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
