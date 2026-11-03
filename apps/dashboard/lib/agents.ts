// The agent roster (spec §5), as nfactory_core.roster.AGENTS names it; a Python test
// keeps the two lists equal.

export interface AgentInfo {
  code: string | null;
  label: string;
  kind: "model" | "code";
}

export const AGENTS: Record<string, AgentInfo> = {
  requirements: { code: "A1", label: "Analyste des besoins", kind: "model" },
  planner: { code: "A2", label: "Planificateur", kind: "model" },
  architect: { code: "A3", label: "Architecte", kind: "model" },
  orchestrator: { code: "A4", label: "Orchestrateur", kind: "code" },
  builder: { code: "A5", label: "Constructeur", kind: "code" },
  automation: { code: "A6", label: "Automaticien", kind: "code" },
  tester: { code: "A7", label: "Testeur", kind: "code" },
  debugger: { code: "A8", label: "Correcteur", kind: "model" },
  reviewer: { code: "A9", label: "Relecteur", kind: "model" },
  security_delivery: { code: "A10", label: "Sécurité et livraison", kind: "code" },
  documenter: { code: null, label: "Rédacteur", kind: "model" },
};

export function agentLabel(role: string): string {
  const agent = AGENTS[role];
  if (!agent) return role;
  return agent.code ? `${agent.code} · ${agent.label}` : agent.label;
}
