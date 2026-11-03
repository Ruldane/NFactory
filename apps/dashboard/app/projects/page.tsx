import type { Metadata } from "next";

import { ProjectList } from "@/components/projects/project-list";

export const metadata: Metadata = { title: "Projets · NFactory" };

export default function ProjectsPage() {
  return (
    <div className="space-y-8">
      <header className="nf-rise">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-coral-deep">Projets</p>
        <h1 className="mt-2 font-display text-5xl text-navy">Tout ce qui sort de l&apos;usine</h1>
      </header>
      <div className="nf-rise [animation-delay:80ms]">
        <ProjectList />
      </div>
    </div>
  );
}
