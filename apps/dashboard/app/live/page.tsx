import type { Metadata } from "next";

import { LiveFactory } from "@/components/live/live-factory";

export const metadata: Metadata = { title: "Usine en direct · NFactory" };

export default function LivePage() {
  return (
    <div className="space-y-10">
      <header className="nf-rise">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-coral-deep">
          Usine en direct
        </p>
        <h1 className="mt-2 font-display text-5xl text-navy">La chaîne, en temps réel</h1>
        <p className="mt-3 max-w-2xl text-navy/70">
          Chaque agent, son état, sa durée et ses corrections, avec le journal du run au fil de
          l&apos;eau.
        </p>
      </header>
      <div className="nf-rise [animation-delay:80ms]">
        <LiveFactory />
      </div>
    </div>
  );
}
