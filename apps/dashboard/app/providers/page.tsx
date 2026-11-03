import type { Metadata } from "next";

import { ProvidersView } from "@/components/providers/providers-view";

export const metadata: Metadata = { title: "Moteurs IA · NFactory" };

export default function ProvidersPage() {
  return (
    <div className="space-y-10">
      <header className="nf-rise">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-coral-deep">Moteurs IA</p>
        <h1 className="mt-2 font-display text-5xl text-navy">Qui répond à vos agents</h1>
        <p className="mt-3 max-w-2xl text-navy/70">
          Connectez des fournisseurs cloud ou un moteur local, puis choisissez lequel répond à
          chaque rôle. Rien n&apos;est appelé sans votre configuration.
        </p>
      </header>
      <div className="nf-rise [animation-delay:80ms]">
        <ProvidersView />
      </div>
    </div>
  );
}
