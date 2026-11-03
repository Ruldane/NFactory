import type { Metadata } from "next";

import { RecipesView } from "@/components/recipes/recipes-view";

export const metadata: Metadata = { title: "Recettes · NFactory" };

export default function RecipesPage() {
  return (
    <div className="space-y-10">
      <header className="nf-rise">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-coral-deep">
          Recettes
        </p>
        <h1 className="mt-2 font-display text-5xl text-navy">
          Refaire ce qui a marché
        </h1>
        <p className="mt-3 max-w-2xl text-navy/70">
          Les runs livrés que votre équipe a gardés. Relancer une recette crée
          un nouveau projet, fabriqué et testé avec les moteurs et les limites
          du moment.
        </p>
      </header>
      <div className="nf-rise [animation-delay:80ms]">
        <RecipesView />
      </div>
    </div>
  );
}
