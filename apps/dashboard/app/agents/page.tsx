import type { Metadata } from "next";

import { AgentTasks } from "@/components/agents/agent-tasks";

export const metadata: Metadata = { title: "Agents de code · NFactory" };

export default function AgentsPage() {
  return (
    <div className="space-y-10">
      <header className="nf-rise">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-coral-deep">Agents de code</p>
        <h1 className="mt-2 font-display text-5xl text-navy">Votre agent, sur votre dépôt</h1>
        <p className="mt-3 max-w-2xl text-navy/70">
          Confiez une petite tâche à Codex, ou passez le relais à votre Claude Code. L&apos;agent
          travaille dans une copie séparée de votre dépôt, sur une branche dédiée : votre dossier
          reste tel quel. Vous voyez le diff, puis NFactory le teste dans son sandbox.
        </p>
      </header>
      <div className="nf-rise [animation-delay:80ms]">
        <AgentTasks />
      </div>
    </div>
  );
}
