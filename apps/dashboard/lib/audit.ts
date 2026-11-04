// French words for the audit log's action slugs (callers of apps/api/app/services/audit.py).

const ACTIONS: Record<string, string> = {
  "run.cancel": "Run annulé",
  "approval.decided": "Approbation décidée",
  "settings.run_limits": "Limites des runs modifiées",
  "routing.update": "Routage des moteurs modifié",
  "provider.configure": "Moteur IA configuré",
  "provider.remove": "Moteur IA retiré",
  "provider.model_set": "Modèle ajouté au catalogue",
  "provider.model_remove": "Modèle retiré du catalogue",
  "knowledge.document_delete": "Document supprimé",
  "knowledge.settings": "Réglages de la base de connaissances modifiés",
  "bridge.pair": "Pont local appairé",
  "bridge.unpair": "Pont local désappairé",
  "agent_task.publish": "Publication d'une tâche d'agent",
  "recipe.save": "Recette enregistrée",
  "recipe.launch": "Recette relancée",
  "recipe.delete": "Recette supprimée",
  "auth.login": "Connexion",
  "auth.logout": "Déconnexion",
  "auth.denied": "Connexion refusée",
  "settings.retention": "Conservation des données modifiée",
  "retention.purge": "Purge des données expirées",
  "member.export": "Export de ses données",
  "member.erased": "Membre effacé",
  "project.deleted": "Projet supprimé",
};

const DECISIONS: Record<string, string> = {
  applied: "Appliqué",
  approved: "Approuvé",
  rejected: "Refusé",
  denied: "Refusé",
  failed: "Échec",
};

export function describeAction(action: string): string {
  return ACTIONS[action] ?? action;
}

export function describeDecision(decision: string | null): string {
  if (!decision) return "—";
  return DECISIONS[decision] ?? decision;
}
