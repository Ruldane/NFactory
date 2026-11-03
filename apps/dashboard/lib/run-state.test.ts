import { describe, expect, it } from "vitest";

import { describeRunState, describeStepState, isTerminalRunState } from "@/lib/run-state";

describe("describeRunState", () => {
  it("gives every run state a French label and a non-color glyph", () => {
    const states = [
      "DRAFT", "PLANNING", "WAITING_FOR_INPUT", "APPROVAL_PENDING", "QUEUED", "RUNNING",
      "REVIEW_PENDING", "COMPLETED", "PARTIAL", "FAILED", "CANCELLED",
    ];
    for (const state of states) {
      const d = describeRunState(state);
      expect(d.label).not.toBe(state);
      expect(d.glyph.length).toBeGreaterThan(0);
    }
  });

  it("never presents a failed run as a success", () => {
    expect(describeRunState("FAILED").tone).toBe("danger");
    expect(describeRunState("COMPLETED").tone).toBe("success");
  });

  it("flags states that need a human", () => {
    expect(describeRunState("APPROVAL_PENDING").tone).toBe("attention");
  });

  it("falls back safely on an unknown state", () => {
    expect(describeRunState("TELEPORTED")).toMatchObject({ label: "TELEPORTED", tone: "neutral" });
  });
});

describe("describeStepState", () => {
  it("distinguishes failed, skipped and pending steps without color", () => {
    const glyphs = ["SUCCEEDED", "FAILED", "SKIPPED", "PENDING", "RUNNING"].map(
      (s) => describeStepState(s).glyph,
    );
    expect(new Set(glyphs).size).toBe(glyphs.length);
  });
});

describe("isTerminalRunState", () => {
  it("separates finished runs from runs that can still change", () => {
    expect(["COMPLETED", "PARTIAL", "FAILED", "CANCELLED"].every(isTerminalRunState)).toBe(true);
    expect(["QUEUED", "RUNNING", "APPROVAL_PENDING"].some(isTerminalRunState)).toBe(false);
  });
});
