"use client";

import { type FormEvent, useState } from "react";

import { ALERT, FIELD, KICKER, SECONDARY } from "@/components/ui/form-styles";
import { useSaveRecipe } from "@/lib/api/recipes";
import type { RunDetail } from "@/lib/api/types";

// Spec F38: keep a delivered run as a recipe of the workspace, to replay it later.
export function SaveRecipe({ run }: { run: RunDetail }) {
  const save = useSaveRecipe();
  const [name, setName] = useState(run.project.title);
  const ready = name.trim() !== "" && !save.isPending;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (ready) save.mutate({ runId: run.id, name: name.trim() });
  }

  return (
    <form onSubmit={submit} className="space-y-3 border-t border-navy/15 pt-6">
      <label className="block space-y-2">
        <span className={KICKER}>Nom de la recette</span>
        <input
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            save.reset();
          }}
          maxLength={120}
          className={`${FIELD} font-sans`}
        />
      </label>
      <p className="text-xs text-navy/60">
        La recette garde le type de projet et cette demande. Relancée depuis «
        Recettes », elle crée un nouveau projet, fabriqué et testé comme un
        premier run.
      </p>
      {save.error ? (
        <p role="alert" className={ALERT}>
          {save.error.message}
        </p>
      ) : null}
      {save.isSuccess ? (
        <p role="status" className="text-sm text-forest">
          Recette enregistrée : retrouvez-la dans « Recettes ».
        </p>
      ) : null}
      <button type="submit" disabled={!ready} className={SECONDARY}>
        {save.isPending ? "Enregistrement…" : "Enregistrer comme recette"}
      </button>
    </form>
  );
}
