import type { Metadata } from "next";

import { NewProjectForm } from "@/components/new/new-project-form";

export const metadata: Metadata = { title: "Nouveau projet · NFactory" };

export default function NewProjectPage() {
  return (
    <div className="space-y-10">
      <header className="nf-rise">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-coral-deep">
          Nouveau projet
        </p>
        <h1 className="mt-2 font-display text-5xl text-navy">Décrivez ce qu&apos;il vous faut</h1>
        <p className="mt-3 max-w-2xl text-navy/70">
          Code ou non-code : une API, un classeur Excel, un document Word… L&apos;usine le
          fabrique, le teste et vous le livre avec une explication.
        </p>
      </header>
      <div className="nf-rise [animation-delay:80ms]">
        <NewProjectForm />
      </div>
    </div>
  );
}
