import { describe, expect, it } from "vitest";

import type { RecentRun, RunEvent } from "@/lib/api/types";
import { filterEvents, pickRun, repairAttempts } from "@/lib/live";

const run = (id: string, state: string): RecentRun => ({
  id,
  project_id: "p",
  project_title: id,
  state,
  is_demo: false,
  created_at: "2026-11-01T10:00:00Z",
  finished_at: null,
  steps: [],
});

const event = (seq: number, type: string, payload: Record<string, unknown> = {}): RunEvent => ({
  seq,
  type,
  step_id: null,
  created_at: "2026-11-01T10:00:00Z",
  payload,
});

describe("pickRun", () => {
  const recent = [run("done", "COMPLETED"), run("busy", "RUNNING"), run("old", "FAILED")];

  it("follows the run the user chose", () => {
    expect(pickRun(recent, "old")).toBe("old");
  });

  it("otherwise follows a run still in progress", () => {
    expect(pickRun(recent, null)).toBe("busy");
    expect(pickRun(recent, "gone")).toBe("busy");
  });

  it("falls back to the most recent run, or none", () => {
    expect(pickRun([run("a", "COMPLETED"), run("b", "FAILED")], null)).toBe("a");
    expect(pickRun([], null)).toBeNull();
  });
});

describe("filterEvents", () => {
  const events = [
    event(1, "run.started"),
    event(2, "step.started", { step: "checks" }),
    event(3, "agent.progress", { agent: "planner" }),
    event(4, "tool.invoked", { check: "Lint (ruff)", exit_code: 1 }),
    event(5, "test.failed", { failed: 1 }),
    event(6, "repair.started", { attempt: 1 }),
    event(7, "tool.invoked", { check: "Lint (ruff)", exit_code: 0 }),
  ];

  it("keeps everything by default", () => {
    expect(filterEvents(events, "all")).toHaveLength(7);
  });

  it("groups by kind", () => {
    expect(filterEvents(events, "agents").map((e) => e.seq)).toEqual([3, 6]);
    expect(filterEvents(events, "checks").map((e) => e.seq)).toEqual([4, 5, 7]);
    expect(filterEvents(events, "steps").map((e) => e.seq)).toEqual([1, 2]);
  });

  it("shows failures, including a check with a non-zero exit code", () => {
    expect(filterEvents(events, "errors").map((e) => e.seq)).toEqual([4, 5]);
  });

  it("counts repair attempts", () => {
    expect(repairAttempts(events)).toBe(1);
  });
});
