"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useRef, useState } from "react";

import { RecipePicker } from "@/components/new/recipe-picker";
import { Skeleton } from "@/components/ui/skeleton";
import { useLaunchProject, useRecipes } from "@/lib/api/queries";
import type { ProjectType } from "@/lib/api/types";

const FIELD =
  "w-full border border-navy/20 bg-cream px-4 py-3 text-navy placeholder:text-navy/40 focus-visible:border-coral-deep focus-visible:outline-none";

export function NewProjectForm() {
  const router = useRouter();
  const recipes = useRecipes();
  const launch = useLaunchProject();
  const [type, setType] = useState<ProjectType | null>(null);
  const [title, setTitle] = useState("");
  const [request, setRequest] = useState("");
  // Made on the first submit, then kept: a retry after a network error reuses it.
  const idempotencyKey = useRef<string | null>(null);

  const ready = type !== null && title.trim() !== "" && request.trim() !== "";

  function submit(event: FormEvent) {
    event.preventDefault();
    if (type === null || !ready || launch.isPending) return;
    idempotencyKey.current ??= crypto.randomUUID();
    launch.mutate(
      { title: title.trim(), type, request: request.trim(), idempotencyKey: idempotencyKey.current },
      { onSuccess: (run) => router.push(`/runs/${run.id}`) },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-8">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <label className="block space-y-2">
          <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-navy/60">
            Votre besoin
          </span>
          <textarea
            value={request}
            onChange={(e) => setRequest(e.target.value)}
            rows={6}
            maxLength={20_000}
            placeholder="Ex. : un classeur qui récapitule les heures de chaque équipe par semaine, avec les totaux et les moyennes."
            className={`${FIELD} resize-y font-sans leading-relaxed`}
          />
        </label>
        <label className="block space-y-2">
          <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-navy/60">
            Nom du projet
          </span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            placeholder="Rapport des heures"
            className={FIELD}
          />
        </label>
      </div>

      {recipes.error ? (
        <div role="alert" className="border-l-4 border-coral-deep bg-coral-deep/8 px-5 py-4 text-sm">
          {recipes.error.message}
        </div>
      ) : recipes.isPending ? (
        <Skeleton className="h-48 bg-navy/8" aria-label="Chargement des types de projet" />
      ) : (
        <RecipePicker recipes={recipes.data.items} value={type} onChange={setType} />
      )}

      {launch.error ? (
        <div role="alert" className="border-l-4 border-coral-deep bg-coral-deep/8 px-5 py-4 text-sm">
          {launch.error.message}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-4">
        <button
          type="submit"
          disabled={!ready || launch.isPending}
          className="bg-eggplant px-6 py-3 font-medium text-cream transition-colors hover:bg-navy focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-coral-deep disabled:cursor-not-allowed disabled:opacity-45"
        >
          {launch.isPending ? "Lancement…" : "Lancer la fabrication"}
        </button>
        <p className="text-sm text-navy/60">
          Le run analyse le besoin, génère le livrable, le vérifie pour de vrai puis le livre.
        </p>
      </div>
    </form>
  );
}
