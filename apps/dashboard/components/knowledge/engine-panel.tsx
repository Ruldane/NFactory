"use client";

import { type FormEvent, useId, useState } from "react";

import { ALERT, FIELD, KICKER, SECONDARY } from "@/components/ui/form-styles";
import { useKnowledgeSettings, useSaveEmbedding } from "@/lib/api/knowledge";
import type { KnowledgeSettings } from "@/lib/api/types";

const LOCAL_MODEL = "empreinte-v1";

// Which engine turns passages into vectors. Changing it re-indexes every document.
export function EnginePanel() {
  const settings = useKnowledgeSettings();
  return (
    <section aria-labelledby="engine-title" className="space-y-4">
      <div>
        <h2 id="engine-title" className="font-display text-2xl text-navy">
          Moteur d&apos;embeddings
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-navy/70">
          Il est choisi indépendamment des modèles qui génèrent. L&apos;empreinte locale ne quitte
          pas ce poste mais ne comprend pas les synonymes ; un vrai modèle (Ollama local ou
          fournisseur connecté) donne une recherche sémantique.
        </p>
      </div>
      {settings.error ? <p role="alert" className={ALERT}>{settings.error.message}</p> : null}
      {settings.data ? <EngineForm key={settings.data.embedding.provider + settings.data.embedding.model} data={settings.data} /> : null}
    </section>
  );
}

function EngineForm({ data }: { data: KnowledgeSettings }) {
  const ids = { provider: useId(), model: useId() };
  const save = useSaveEmbedding();
  const [provider, setProvider] = useState(data.embedding.provider);
  const [model, setModel] = useState(data.embedding.provider === "local" ? "" : data.embedding.model);
  const local = provider === "local";
  const unavailable = data.options.filter((o) => !o.available && o.reason);

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate({ provider, model: local ? LOCAL_MODEL : model.trim() });
  }

  return (
    <div className="space-y-4">
      {data.index_error ? (
        <p role="alert" className={ALERT}>
          L&apos;indexation s&apos;est arrêtée : {data.index_error}
        </p>
      ) : null}
      <p className="font-mono text-xs text-navy/70">
        {data.index.embedded} / {data.index.total} passages vectorisés
      </p>
      <form onSubmit={submit} className="grid gap-4 md:grid-cols-[16rem_1fr_auto] md:items-end">
        <div className="space-y-1">
          <label htmlFor={ids.provider} className={KICKER}>
            Moteur
          </label>
          <select id={ids.provider} value={provider} onChange={(e) => setProvider(e.target.value)} className={FIELD}>
            {data.options.map((option) => (
              <option key={option.provider} value={option.provider} disabled={!option.available}>
                {option.label}
                {option.local ? "" : " (distant)"}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label htmlFor={ids.model} className={KICKER}>
            Modèle d&apos;embeddings
          </label>
          <input
            id={ids.model}
            value={local ? LOCAL_MODEL : model}
            onChange={(e) => setModel(e.target.value)}
            disabled={local}
            placeholder="identifiant du modèle"
            className={FIELD}
          />
        </div>
        <button
          type="submit"
          className={SECONDARY}
          disabled={save.isPending || (!local && !model.trim())}
        >
          Utiliser ce moteur
        </button>
      </form>
      {save.error ? <p role="alert" className={ALERT}>{save.error.message}</p> : null}
      {unavailable.length ? (
        <ul className="space-y-1 text-xs text-navy/60">
          {unavailable.map((option) => (
            <li key={option.provider}>
              <span aria-hidden>○ </span>
              {option.reason}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
