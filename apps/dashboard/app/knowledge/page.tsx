import type { Metadata } from "next";

import { KnowledgeView } from "@/components/knowledge/knowledge-view";

export const metadata: Metadata = { title: "Base de connaissances · NFactory" };

export default function KnowledgePage() {
  return (
    <div className="space-y-10">
      <header className="nf-rise">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-coral-deep">
          Base de connaissances
        </p>
        <h1 className="mt-2 font-display text-5xl text-navy">Ce que vos agents peuvent citer</h1>
        <p className="mt-3 max-w-2xl text-navy/70">
          Procédures, conventions, README, code de référence : chaque run cherche ici, cite ses
          sources à la ligne près, et traite ces textes comme des données, jamais comme des ordres.
        </p>
      </header>
      <div className="nf-rise [animation-delay:80ms]">
        <KnowledgeView />
      </div>
    </div>
  );
}
