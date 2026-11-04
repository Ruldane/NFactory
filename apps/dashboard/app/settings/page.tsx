import type { Metadata } from "next";

import { SettingsView } from "@/components/settings/settings-view";

export const metadata: Metadata = { title: "Réglages · NFactory" };

export default function SettingsPage() {
  return (
    <div className="space-y-10">
      <header className="nf-rise">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-coral-deep">Réglages</p>
        <h1 className="mt-2 font-display text-5xl text-navy">Votre usine</h1>
        <p className="mt-3 max-w-2xl text-navy/70">
          Ce qui tourne sur ce poste, les limites de chaque nouveau run, la conservation des données et les membres.
        </p>
      </header>
      <div className="nf-rise [animation-delay:80ms]">
        <SettingsView />
      </div>
    </div>
  );
}
