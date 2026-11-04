import { describe, expect, it } from "vitest";

import { describeAction, describeDecision } from "@/lib/audit";

describe("audit words", () => {
  it("names known actions and keeps unknown slugs visible", () => {
    expect(describeAction("run.cancel")).toBe("Run annulé");
    expect(describeAction("future.action")).toBe("future.action");
  });

  it("names the recipe actions", () => {
    expect(describeAction("recipe.save")).toBe("Recette enregistrée");
    expect(describeAction("recipe.launch")).toBe("Recette relancée");
    expect(describeAction("recipe.delete")).toBe("Recette supprimée");
  });

  it("names the sign-in actions", () => {
    expect(describeAction("auth.login")).toBe("Connexion");
    expect(describeAction("auth.logout")).toBe("Déconnexion");
    expect(describeAction("auth.denied")).toBe("Connexion refusée");
  });

  it("names the data-rights actions (ADR-0015)", () => {
    expect(describeAction("settings.retention")).toBe("Conservation des données modifiée");
    expect(describeAction("retention.purge")).toBe("Purge des données expirées");
    expect(describeAction("member.export")).toBe("Export de ses données");
    expect(describeAction("member.erased")).toBe("Membre effacé");
    expect(describeAction("project.deleted")).toBe("Projet supprimé");
  });

  it("names decisions, and a missing one as a dash", () => {
    expect(describeDecision("rejected")).toBe("Refusé");
    expect(describeDecision(null)).toBe("—");
  });
});
