import { describe, expect, it } from "vitest";

import type { RunEvent } from "@/lib/api/types";
import { describeEvent, isFinalEvent, mergeEvents } from "@/lib/run-events";

const event = (seq: number, type: string, payload: Record<string, unknown> = {}): RunEvent => ({
  seq,
  type,
  step_id: null,
  created_at: "2026-11-01T10:00:00Z",
  payload,
});

describe("mergeEvents", () => {
  it("keeps one copy of each event, in sequence order", () => {
    // A reconnecting stream may replay events the page already holds.
    const merged = mergeEvents(
      [event(1, "run.created"), event(3, "step.started")],
      [event(2, "run.started"), event(3, "step.started")],
    );
    expect(merged.map((e) => e.seq)).toEqual([1, 2, 3]);
  });
});

describe("describeEvent", () => {
  it("tells what happened in French", () => {
    expect(describeEvent(event(1, "step.started", { step: "build" }))).toBe(
      "Construction : démarrage",
    );
    expect(describeEvent(event(2, "test.passed", { passed: 7, total: 7 }))).toBe(
      "Tests réussis : 7 / 7",
    );
    expect(describeEvent(event(3, "test.failed", { passed: 5, total: 7 }))).toBe(
      "Tests en échec : 5 / 7 réussis",
    );
    // A worker restart resumes the run (RUNNING again, from its checkpoint).
    expect(describeEvent(event(9, "run.state_changed", { state: "RUNNING", resumed: true }))).toBe(
      "Run repris après interruption",
    );
    expect(describeEvent(event(4, "repair.started", { attempt: 2 }))).toBe(
      "Correction automatique, tentative 2",
    );
    expect(describeEvent(event(5, "artifact.created", { filename: "a.zip" }))).toBe(
      "Livrable enregistré : a.zip",
    );
    expect(describeEvent(event(6, "run.failed", { error: "boom" }))).toBe("Run en échec : boom");
  });

  it("traces repairs and the secret scan", () => {
    const applied = { attempt: 1, files: ["app/a.py", "app/b.py"], cause: "Import manquant" };
    expect(describeEvent(event(1, "repair.applied", applied))).toBe(
      "Correction 1 appliquée (2 fichiers) : Import manquant",
    );
    expect(describeEvent(event(2, "repair.abandoned", { attempt: 4, reason: "limite de tentatives atteinte" }))).toBe(
      "Correction abandonnée : limite de tentatives atteinte",
    );
    expect(describeEvent(event(3, "security.scanned", { files: 12, findings: 0 }))).toBe(
      "Recherche de secrets : aucun secret dans 12 fichiers",
    );
    expect(describeEvent(event(4, "security.scanned", { files: 12, findings: 2 }))).toBe(
      "Recherche de secrets : 2 secrets probables (valeurs masquées)",
    );
  });

  it("sums up what a change request changed", () => {
    const payload = { parent_run_id: "run_a", added: 0, modified: 3, removed: 1 };
    expect(describeEvent(event(1, "changes.computed", payload))).toBe(
      "Modifications depuis run_a : 0 ajouté, 3 modifiés, 1 supprimé",
    );
  });

  it("describes engine failures and the user's decision", () => {
    const failed = { role: "reviewer", message: "OpenAI : quota ou crédit épuisé." };
    expect(describeEvent(event(1, "provider.failed", failed))).toBe(
      "Moteur en échec (Relecteur) : OpenAI : quota ou crédit épuisé.",
    );
    expect(describeEvent(event(2, "approval.requested", {}))).toBe(
      "Run en pause : votre décision est attendue",
    );
    expect(
      describeEvent(event(3, "approval.resolved", { decision: "approved", provider: "ollama_local", model: "m" })),
    ).toBe("Décision : reprise avec ollama_local · m");
    expect(describeEvent(event(4, "approval.resolved", { decision: "rejected" }))).toBe(
      "Décision : run arrêté",
    );
  });

  it("falls back to the raw type for unknown events", () => {
    expect(describeEvent(event(1, "something.new"))).toBe("something.new");
  });
});

describe("isFinalEvent", () => {
  it("recognises the events that end a run", () => {
    const finals = ["run.completed", "run.failed", "run.cancelled"];
    expect(finals.every((type) => isFinalEvent(event(1, type)))).toBe(true);
    expect(isFinalEvent(event(1, "step.completed"))).toBe(false);
  });
});
