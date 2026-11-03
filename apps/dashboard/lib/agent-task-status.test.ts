import { describe, expect, it } from "vitest";

import { describeAgentEvent, describeTaskStatus, isTaskActive, publicationFacts } from "@/lib/agent-task-status";

describe("describeTaskStatus", () => {
  it("gives every status a glyph and a French label", () => {
    for (const status of ["preparing", "running", "succeeded", "no_changes", "failed", "cancelled", "discarded"]) {
      const state = describeTaskStatus(status);
      expect(state.glyph).not.toBe("");
      expect(state.label).not.toBe(status);
    }
  });

  it("does not call a run that changed nothing a success", () => {
    expect(describeTaskStatus("no_changes").tone).toBe("attention");
    expect(describeTaskStatus("succeeded").tone).toBe("success");
  });

  it("knows when a task is still going", () => {
    expect(isTaskActive("running")).toBe(true);
    expect(isTaskActive("preparing")).toBe(true);
    expect(isTaskActive("succeeded")).toBe(false);
  });
});

describe("describeAgentEvent", () => {
  it("reads a finished command with its exit code", () => {
    expect(describeAgentEvent({ type: "command", command: "pytest -q", status: "failed", exit_code: 1 })).toEqual({
      glyph: "✗",
      label: "Commande",
      text: "pytest -q",
      detail: "code 1",
    });
  });

  it("lists the files an agent changed", () => {
    const event = describeAgentEvent({
      type: "file_change",
      changes: [
        { path: "calc.py", kind: "update" },
        { path: "tests/test_calc.py", kind: "add" },
      ],
    });
    expect(event.text).toBe("calc.py, tests/test_calc.py");
  });

  it("shows token usage at the end", () => {
    const detail = describeAgentEvent({ type: "completed", usage: { input_tokens: 1200, output_tokens: 45 } }).detail;
    // fr-FR groups thousands with a narrow no-break space.
    expect(detail?.replace(/\s/gu, " ")).toBe("1 200 jetons lus · 45 écrits");
  });
});

describe("visibleEvents", () => {
  it("keeps one line per command: the finished one replaces its start", async () => {
    const { visibleEvents } = await import("@/lib/agent-task-status");
    const events = [
      { type: "command" as const, command: "pytest -q", status: "in_progress", exit_code: null },
      { type: "command" as const, command: "pytest -q", status: "failed", exit_code: 1 },
      { type: "command" as const, command: "pytest -q", status: "in_progress" },
    ];

    expect(visibleEvents(events)).toEqual([events[1], events[2]]);
  });

  it("does not read a missing exit code as a result", () => {
    expect(describeAgentEvent({ type: "command", command: "ls", status: "in_progress", exit_code: null }).detail).toBeUndefined();
  });
});

describe("describeCheckStatus", () => {
  it("gives every check status a glyph and a French label", async () => {
    const { describeCheckStatus } = await import("@/lib/agent-task-status");
    for (const status of ["queued", "running", "passed", "failed", "not_tested", "error"]) {
      const state = describeCheckStatus(status);
      expect(state.glyph).not.toBe("");
      expect(state.label).not.toBe(status);
    }
    expect(describeCheckStatus("passed").tone).toBe("success");
    expect(describeCheckStatus("not_tested").tone).toBe("attention");
  });

  it("names a handoff waiting for the user", () => {
    expect(describeTaskStatus("awaiting_user").label).toBe("En attente de vous");
  });
});

describe("publicationFacts", () => {
  it("lists the four facts in order, done up to the state GitHub confirmed", () => {
    expect(publicationFacts("pushed")).toEqual([
      { key: "local_commit_created", label: "Commit local créé", done: true },
      { key: "pushed", label: "Branche poussée sur GitHub", done: true },
      { key: "pr_created", label: "PR brouillon ouverte", done: false },
      { key: "merged", label: "Fusionnée par un humain", done: false },
    ]);
  });

  it("marks nothing done when no fact is confirmed", () => {
    expect(publicationFacts(null).every((fact) => !fact.done)).toBe(true);
  });
});
