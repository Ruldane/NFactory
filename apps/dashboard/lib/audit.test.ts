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

  it("names decisions, and a missing one as a dash", () => {
    expect(describeDecision("rejected")).toBe("Refusé");
    expect(describeDecision(null)).toBe("—");
  });
});
