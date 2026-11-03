"use client";

// A provider's model catalog: what discovery found plus what the admin added. Prices are
// typed by the admin; a model without a price gives a run cost of "Non mesuré".

import { type FormEvent, useId, useState } from "react";

import { ALERT, FIELD, KICKER, SECONDARY } from "@/components/ui/form-styles";
import { useCatalog, useDeleteModel, useSaveModel } from "@/lib/api/providers";
import type { CatalogModel } from "@/lib/api/types";

const price = (model: CatalogModel) =>
  model.pricing
    ? `${model.pricing.input_per_mtok} $ / ${model.pricing.output_per_mtok} $ par M jetons`
    : "Prix non renseigné";

export function ModelCatalog({ kind }: { kind: string }) {
  const catalog = useCatalog(kind);
  const save = useSaveModel(kind);
  const remove = useDeleteModel(kind);
  const id = useId();
  const [modelId, setModelId] = useState("");
  const [input, setInput] = useState("");
  const [output, setOutput] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    const pricing =
      input !== "" && output !== ""
        ? { input_per_mtok: Number(input), output_per_mtok: Number(output), cached_input_per_mtok: null }
        : null;
    save.mutate(
      { modelId: modelId.trim(), pricing },
      {
        onSuccess: () => {
          setModelId("");
          setInput("");
          setOutput("");
        },
      },
    );
  }

  const models = catalog.data ?? [];
  return (
    <div className="space-y-3">
      <p className={KICKER}>Catalogue des modèles</p>
      {catalog.isPending ? null : models.length === 0 ? (
        <p className="text-sm text-navy/60">
          Aucun modèle au catalogue : un test de connexion le remplit si le fournisseur publie sa
          liste, sinon ajoutez-en un ci-dessous.
        </p>
      ) : (
        <ul className="divide-y divide-navy/10 border-y border-navy/10">
          {models.map((model) => (
            <li key={model.model_id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
              <span className="font-mono text-navy">{model.model_id}</span>
              <span className="font-mono text-[11px] uppercase tracking-wider text-navy/50">
                {model.source === "discovered" ? "découvert" : "ajouté"}
              </span>
              <span className="text-navy/65">{price(model)}</span>
              <button
                type="button"
                onClick={() => remove.mutate(model.model_id)}
                className="ml-auto text-xs text-coral-deep underline-offset-2 hover:underline"
              >
                Retirer {model.model_id}
              </button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={submit} className="grid gap-2 md:grid-cols-[2fr_1fr_1fr_auto] md:items-end">
        <label className="space-y-1">
          <span className={`block ${KICKER}`}>Identifiant du modèle</span>
          <input
            id={`${id}-model`}
            required
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            className={FIELD}
          />
        </label>
        <label className="space-y-1">
          <span className={`block ${KICKER}`}>Entrée $/M</span>
          <input
            type="number"
            min={0}
            step="any"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className={FIELD}
          />
        </label>
        <label className="space-y-1">
          <span className={`block ${KICKER}`}>Sortie $/M</span>
          <input
            type="number"
            min={0}
            step="any"
            value={output}
            onChange={(e) => setOutput(e.target.value)}
            className={FIELD}
          />
        </label>
        <button type="submit" disabled={save.isPending} className={SECONDARY}>
          Ajouter au catalogue
        </button>
      </form>
      {save.error ? <div className={ALERT}>{save.error.message}</div> : null}
    </div>
  );
}
