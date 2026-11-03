"use client";

// The workspace's reusable recipes (spec F38). Replaying one creates a new project and
// launches its run; that run is built and tested like any other.

import Link from "next/link";
import { useRouter } from "next/navigation";

import { projectTypeLabel } from "@/components/projects/project-types";
import { ALERT, DANGER, KICKER, PRIMARY } from "@/components/ui/form-styles";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useDeleteRecipe,
  useReplayRecipe,
  useSavedRecipes,
} from "@/lib/api/recipes";
import type { SavedRecipe } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";

function uses(recipe: SavedRecipe): string {
  if (recipe.uses === 0) return "Jamais relancée";
  const times = recipe.uses === 1 ? "1 fois" : `${recipe.uses} fois`;
  const last = recipe.last_used_at
    ? `, dernière fois le ${formatDateTime(recipe.last_used_at)}`
    : "";
  return `Relancée ${times}${last}`;
}

function RecipeCard({ recipe }: { recipe: SavedRecipe }) {
  const router = useRouter();
  const replay = useReplayRecipe();
  const remove = useDeleteRecipe();
  const titleId = `recipe-${recipe.id}`;
  const busy = replay.isPending || remove.isPending;

  function launch() {
    // A fresh key per click; the API answers a replayed key with the same run.
    replay.mutate(
      { recipeId: recipe.id, idempotencyKey: crypto.randomUUID() },
      { onSuccess: (run) => router.push(`/runs/${run.id}`) },
    );
  }

  return (
    <article
      aria-labelledby={titleId}
      className="space-y-3 border border-navy/15 bg-cream px-5 py-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={titleId} className="font-display text-2xl text-navy">
          {recipe.name}
        </h2>
        <span className={KICKER}>{projectTypeLabel(recipe.project_type)}</span>
      </div>
      {recipe.description ? (
        <p className="text-sm text-navy/70">{recipe.description}</p>
      ) : null}
      <blockquote className="border-l-4 border-coral pl-4 text-navy/80 italic">
        {recipe.request}
      </blockquote>
      <p className="font-mono text-[11px] text-navy/55">
        Créée le {formatDateTime(recipe.created_at)} · {uses(recipe)}
        {recipe.source_run_id ? (
          <>
            {" · "}
            <Link
              href={`/runs/${recipe.source_run_id}`}
              className="underline underline-offset-2"
            >
              run d&apos;origine
            </Link>
          </>
        ) : null}
      </p>
      {replay.error || remove.error ? (
        <p role="alert" className={ALERT}>
          {(replay.error ?? remove.error)?.message}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          disabled={busy}
          onClick={launch}
          className={PRIMARY}
        >
          {replay.isPending ? "Lancement…" : "Relancer"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => remove.mutate(recipe.id)}
          className={DANGER}
        >
          Supprimer
        </button>
      </div>
    </article>
  );
}

export function RecipesView() {
  const recipes = useSavedRecipes();
  if (recipes.isPending) return <Skeleton className="h-40" />;
  if (recipes.isError) {
    return (
      <p role="alert" className={ALERT}>
        {recipes.error.message}
      </p>
    );
  }
  if (recipes.data.items.length === 0) {
    return (
      <p className="text-navy/70">
        Aucune recette pour l&apos;instant. Ouvrez un run livré et choisissez «
        Enregistrer comme recette ».
      </p>
    );
  }
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      {recipes.data.items.map((recipe) => (
        <RecipeCard key={recipe.id} recipe={recipe} />
      ))}
    </div>
  );
}
