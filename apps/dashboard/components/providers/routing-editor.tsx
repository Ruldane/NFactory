"use client";

// Which engine answers for which agent role in new runs. Only connected engines can be
// picked; a launched run keeps the engines it started with.

import { type FormEvent, useId, useState } from "react";

import { ALERT, FIELD, KICKER, PRIMARY } from "@/components/ui/form-styles";
import { Skeleton } from "@/components/ui/skeleton";
import { useCatalog, useRouting, useSaveRouting } from "@/lib/api/providers";
import type { Engine, Fallback, ProviderView, RoutingView } from "@/lib/api/types";

type Draft = { provider: string; model: string };
const EMPTY: Draft = { provider: "", model: "" };

const toDraft = (engine: Engine | null | undefined): Draft => engine ?? EMPTY;
const toEngine = (draft: Draft): Engine | null =>
  draft.provider && draft.model.trim() ? { provider: draft.provider, model: draft.model.trim() } : null;

export function RoutingEditor({ providers }: { providers: ProviderView[] }) {
  const routing = useRouting();
  if (routing.error) return <div role="alert" className={ALERT}>{routing.error.message}</div>;
  if (!routing.data) return <Skeleton className="h-40 bg-navy/8" aria-label="Chargement du routage" />;
  const connected = providers.filter((p) => p.available && p.status === "connected");
  return <RoutingForm view={routing.data} connected={connected} />;
}

function RoutingForm({ view, connected }: { view: RoutingView; connected: ProviderView[] }) {
  const save = useSaveRouting();
  const [defaultEngine, setDefault] = useState<Draft>(toDraft(view.routing.default));
  const [roles, setRoles] = useState<Record<string, Draft>>(() =>
    Object.fromEntries(view.roles.map((r) => [r.id, toDraft(view.routing.roles[r.id])])),
  );
  const [fallback, setFallback] = useState<Fallback>(view.routing.fallback);
  const [localOnly, setLocalOnly] = useState(view.routing.local_only);

  function submit(event: FormEvent) {
    event.preventDefault();
    const overrides: Record<string, Engine> = {};
    for (const [role, draft] of Object.entries(roles)) {
      const engine = toEngine(draft);
      if (engine) overrides[role] = engine;
    }
    save.mutate({ default: toEngine(defaultEngine), roles: overrides, fallback, local_only: localOnly });
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      {connected.length === 0 ? (
        <p className="text-sm text-navy/70">
          Aucun moteur connecté : configurez un fournisseur puis testez sa connexion. Sans
          routage, les runs utilisent le modèle de démonstration si le mode démo est actif.
        </p>
      ) : null}
      <EnginePicker
        label="par défaut"
        providerLabel="Fournisseur par défaut"
        modelLabel="Modèle par défaut"
        empty="Aucun"
        value={defaultEngine}
        onChange={setDefault}
        connected={connected}
      />
      <div className="space-y-3">
        <p className={KICKER}>Par rôle (facultatif)</p>
        {view.roles.map((role) => (
          <EnginePicker
            key={role.id}
            label={role.label}
            providerLabel={`Fournisseur — ${role.label}`}
            modelLabel={`Modèle — ${role.label}`}
            empty="Moteur par défaut"
            value={roles[role.id] ?? EMPTY}
            onChange={(draft) => setRoles((current) => ({ ...current, [role.id]: draft }))}
            connected={connected}
          />
        ))}
      </div>
      <fieldset className="space-y-2">
        <legend className={KICKER}>Si un moteur échoue</legend>
        <p className="text-sm text-navy/70">
          Les erreurs passagères sont réessayées. Un moteur en échec n&apos;est jamais remplacé sans
          votre accord.
        </p>
        <label className="flex items-center gap-2 text-sm text-navy">
          <input
            type="radio"
            name="fallback"
            checked={fallback === "ask_user"}
            onChange={() => setFallback("ask_user")}
          />
          Mettre le run en pause et me demander quoi faire (recommandé)
        </label>
        <label className="flex items-center gap-2 text-sm text-navy">
          <input
            type="radio"
            name="fallback"
            checked={fallback === "none"}
            onChange={() => setFallback("none")}
          />
          Arrêter le run en échec
        </label>
      </fieldset>
      <label className="flex items-center gap-2 text-sm text-navy">
        <input type="checkbox" checked={localOnly} onChange={(e) => setLocalOnly(e.target.checked)} />
        Local uniquement : refuser tout moteur distant au lancement
      </label>
      {save.error ? <div role="alert" className={ALERT}>{save.error.message}</div> : null}
      <div className="flex flex-wrap items-center gap-4">
        <button type="submit" disabled={save.isPending} className={PRIMARY}>
          Enregistrer le routage
        </button>
        {save.isSuccess ? (
          <p role="status" className="text-sm text-forest">
            ✓ Routage enregistré. Il s&apos;applique aux prochains runs.
          </p>
        ) : null}
      </div>
    </form>
  );
}

function EnginePicker({
  label,
  providerLabel,
  modelLabel,
  empty,
  value,
  onChange,
  connected,
}: {
  label: string;
  providerLabel: string;
  modelLabel: string;
  empty: string;
  value: Draft;
  onChange: (draft: Draft) => void;
  connected: ProviderView[];
}) {
  const id = useId();
  const catalog = useCatalog(value.provider, value.provider !== "");
  return (
    <div className="grid gap-2 md:grid-cols-[10rem_1fr_1fr] md:items-center">
      <span className="text-sm text-navy/75">{label}</span>
      <select
        aria-label={providerLabel}
        value={value.provider}
        onChange={(e) => onChange({ provider: e.target.value, model: "" })}
        className={FIELD}
      >
        <option value="">{empty}</option>
        {connected.map((p) => (
          <option key={p.kind} value={p.kind}>
            {p.label}
          </option>
        ))}
      </select>
      <input
        aria-label={modelLabel}
        list={`${id}-models`}
        disabled={value.provider === ""}
        value={value.model}
        onChange={(e) => onChange({ ...value, model: e.target.value })}
        className={FIELD}
      />
      <datalist id={`${id}-models`}>
        {(catalog.data ?? []).map((m) => (
          <option key={m.model_id} value={m.model_id} />
        ))}
      </datalist>
    </div>
  );
}
