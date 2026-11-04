"use client";

import { type FormEvent, useState } from "react";

import { FIELD, KICKER } from "@/components/settings/styles";
import { useSaveRetention } from "@/lib/api/queries";
import type { RetentionPolicy, WorkspaceSettings } from "@/lib/api/types";

const DURATIONS: { key: keyof RetentionPolicy; label: string; help: string }[] = [
  {
    key: "runs_days",
    label: "Runs terminés (jours)",
    help: "Un run terminé depuis plus longtemps est supprimé, avec ses livrables et ses traces. Un run actif n'est jamais supprimé.",
  },
  {
    key: "audit_days",
    label: "Journal d'audit (jours)",
    help: "La CNIL recommande de garder les journaux de 6 mois à 1 an.",
  },
];

// ADR-0015: an empty field keeps forever, and nothing is deleted until the owner chooses.
export function RetentionForm({ settings }: { settings: WorkspaceSettings }) {
  const [values, setValues] = useState<Record<keyof RetentionPolicy, string>>({
    runs_days: settings.retention.runs_days?.toString() ?? "",
    audit_days: settings.retention.audit_days?.toString() ?? "",
  });
  const save = useSaveRetention();

  function submit(event: FormEvent) {
    event.preventDefault();
    const days = (value: string) => (value.trim() === "" ? null : Number(value));
    save.mutate({ runs_days: days(values.runs_days), audit_days: days(values.audit_days) });
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <div className="grid gap-6 md:grid-cols-2">
        {DURATIONS.map(({ key, label, help }) => {
          const bounds = settings.retention_bounds[key];
          return (
            <div key={key} className="space-y-2">
              <label htmlFor={`retention-${key}`} className={`block ${KICKER}`}>
                {label}
              </label>
              <input
                id={`retention-${key}`}
                aria-describedby={`retention-${key}-help`}
                type="number"
                min={bounds.min}
                max={bounds.max}
                placeholder="Conserver sans limite"
                value={values[key]}
                onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.value }))}
                className={FIELD}
              />
              <p id={`retention-${key}-help`} className="text-sm text-navy/60">
                {help} Entre {bounds.min} et {bounds.max} jours ; vide : conserver sans limite.
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
          Enregistrer la conservation
        </button>
        {save.isSuccess ? (
          <p className="text-sm text-forest">
            ✓ Conservation enregistrée. La purge passe chaque nuit à 3 h 15.
          </p>
        ) : (
          <p className="text-sm text-navy/60">Les sessions de connexion expirées sont toujours supprimées.</p>
        )}
      </div>
    </form>
  );
}
