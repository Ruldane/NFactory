// The NFactory metrics of spec §14.1 as the overview shows them: a French label, how the
// value is displayed, and the query it comes from (computed by the API in
// app/services/metrics.py).

import type { FactoryMetrics } from "@/lib/api/types";
import { formatCost, formatPercent, formatWait } from "@/lib/format";

export interface MetricDefinition {
  key: keyof FactoryMetrics;
  label: string;
  format: (value: number | null) => string;
  source: string;
  alertWhenAboveZero?: boolean;
}

const count = (value: number | null) => (value === null ? "—" : String(value));

export const FACTORY_METRICS: MetricDefinition[] = [
  {
    key: "end_to_end_delivery_rate",
    label: "Livraison de bout en bout",
    format: formatPercent,
    source:
      "Part des runs terminés dont l'état final est COMPLETED (tests réels passés).",
  },
  {
    key: "first_pass_test_rate",
    label: "Tests verts du premier coup",
    format: formatPercent,
    source:
      "Parmi les runs dont les tests ont tourné, part sans aucun événement test.failed.",
  },
  {
    key: "repair_success_rate",
    label: "Réparations réussies",
    format: formatPercent,
    source:
      "Parmi les runs passés par la boucle de réparation (repair.started), part livrée (COMPLETED).",
  },
  {
    key: "human_intervention_count",
    label: "Interventions humaines",
    format: count,
    source:
      "Nombre de validations tranchées par une personne (table approvals, statut ≠ pending).",
  },
  {
    key: "cost_per_successful_delivery",
    label: "Coût par livraison réussie",
    format: formatCost,
    source:
      "Somme des coûts estimés des runs, divisée par le nombre de runs COMPLETED.",
  },
  {
    key: "critical_policy_violation_count",
    label: "Violations critiques",
    format: count,
    source:
      "Runs livrés dont le scan de secrets (security.scanned) a trouvé quelque chose. Objectif : zéro.",
    alertWhenAboveZero: true,
  },
  {
    key: "time_to_preview_seconds",
    label: "Délai jusqu'à l'aperçu",
    format: formatWait,
    source:
      "Non mesuré : aucun événement n'enregistre encore le premier affichage d'un aperçu.",
  },
  {
    key: "time_to_draft_pr_seconds",
    label: "Délai jusqu'à la PR brouillon",
    format: formatWait,
    source:
      "Non mesuré : les PR brouillon viennent des tâches d'agents de code, pas encore reliées à un run.",
  },
];

export const PERIODS = [
  { value: "", label: "Toute la période" },
  { value: "7", label: "7 derniers jours" },
  { value: "30", label: "30 derniers jours" },
  { value: "90", label: "90 derniers jours" },
];
