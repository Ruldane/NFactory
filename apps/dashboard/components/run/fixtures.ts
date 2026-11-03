// Shared test data for the run page components (not imported by app code).

import type { Artifact, RunDetail, RunStep } from "@/lib/api/types";

const step = (name: string, state: string, extra: Partial<RunStep> = {}): RunStep => ({
  id: `step_${name}`,
  position: 0,
  name,
  agent_role: name,
  state,
  attempts: state === "PENDING" ? 0 : 1,
  output: {},
  started_at: state === "PENDING" ? null : "2026-11-01T10:00:00Z",
  ended_at: state === "SUCCEEDED" || state === "FAILED" ? "2026-11-01T10:00:12Z" : null,
  error: null,
  ...extra,
});

export const runningRun: RunDetail = {
  id: "run_1",
  project: { id: "proj_1", title: "Rapport des heures", type: "excel" },
  recipe: "excel-automation",
  model: "demo",
  engines: { requirements: { provider: "demo", model: "fake-demo-1" } },
  pending_approval: null,
  request: "Un rapport des heures par équipe",
  parent_run_id: null,
  state: "RUNNING",
  error: null,
  cost_estimate_usd: null,
  budget: { max_llm_calls: 80, max_agent_steps: 100, max_repair_attempts: 3 },
  trace_id: "0123abcd456789ef0123abcd456789ef",
  is_demo: false,
  created_at: "2026-11-01T10:00:00Z",
  started_at: "2026-11-01T10:00:01Z",
  finished_at: null,
  steps: [
    step("requirements", "SUCCEEDED"),
    step("build", "SUCCEEDED"),
    step("checks", "SUCCEEDED", {
      output: {
        checks: [
          { name: "Lint (ruff)", stage: "static", ok: true, detail: "" },
          { name: "Génération du classeur", stage: "build", ok: true, detail: "" },
        ],
      },
    }),
    step("tests", "FAILED", {
      attempts: 4,
      error: "Échec après 3 tentative(s) de correction : Tests (pytest) : assert 1 == 2",
      output: {
        checks: [{ name: "Tests (pytest)", stage: "tests", ok: false, detail: "assert 1 == 2" }],
        report: {
          passed: 5,
          failed: 1,
          errors: 0,
          skipped: 0,
          total: 6,
          ok: false,
          failures: [{ name: "test_totals", message: "assert 1 == 2" }],
        },
      },
    }),
    step("package", "PENDING"),
  ],
};

export const completedRun: RunDetail = {
  ...runningRun,
  state: "COMPLETED",
  finished_at: "2026-11-01T10:01:30Z",
  steps: [
    ...runningRun.steps.map((s) => ({ ...s, state: "SUCCEEDED", error: null })),
    step("docs", "SUCCEEDED", {
      output: {
        explanation: {
          summary: "Ce classeur calcule les heures par équipe.",
          generated: ["Le classeur rapport-des-heures.xlsx", "Le script build_report.py"],
          verify: ["Les totaux de la feuille Synthèse"],
          limits: [],
        },
      },
    }),
  ],
};

export const artifacts: Artifact[] = [
  {
    id: "art_1",
    filename: "rapport-des-heures.xlsx",
    mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    size: 9014,
    checksum: "sha256:abc",
    created_at: "2026-11-01T10:01:29Z",
    download_url: "/api/v1/artifacts/art_1/download",
  },
  {
    id: "art_2",
    filename: "rapport-des-heures.zip",
    mime: "application/zip",
    size: 13828,
    checksum: "sha256:def",
    created_at: "2026-11-01T10:01:29Z",
    download_url: "/api/v1/artifacts/art_2/download",
  },
];
