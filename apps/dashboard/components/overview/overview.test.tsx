import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Overview } from "@/components/overview/overview";
import type { DashboardSummary } from "@/lib/api/types";

const calls = {
  calls: 3,
  failures: 0,
  latency_p50_s: 2,
  latency_p95_s: 2.9,
  input_tokens: 300,
  output_tokens: 60,
  cost_usd: 0.1,
  cost_complete: false,
};

const demoSummary: DashboardSummary = {
  filters: { days: null, project_type: null },
  demo_data: true,
  projects: 4,
  runs: {
    total: 4,
    active: 1,
    completed: 2,
    partial: 0,
    failed: 1,
    cancelled: 0,
  },
  success_rate: 2 / 3,
  avg_duration_seconds: 560,
  cost_estimate_usd: 0.71,
  approvals_pending: 1,
  recent_runs: [
    {
      id: "run_demo_kpi",
      project_id: "proj_demo_kpi",
      project_title: "Rapport KPI hebdomadaire",
      state: "FAILED",
      is_demo: true,
      created_at: "2026-10-30T09:00:00Z",
      finished_at: "2026-10-30T09:09:00Z",
      steps: [
        { name: "tests", agent_role: "tester", state: "FAILED", attempts: 4 },
      ],
    },
  ],
  metrics: {
    end_to_end_delivery_rate: 2 / 3,
    first_pass_test_rate: 1 / 3,
    repair_success_rate: 0.5,
    time_to_preview_seconds: null,
    time_to_draft_pr_seconds: null,
    human_intervention_count: 1,
    cost_per_successful_delivery: 0.2,
    critical_policy_violation_count: 0,
  },
  providers: [
    { provider: "anthropic", model: "m1", ...calls },
    {
      provider: "openai",
      model: "m2",
      ...calls,
      calls: 0,
      failures: 1,
      latency_p50_s: null,
      latency_p95_s: null,
      cost_usd: null,
    },
  ],
  agents: [{ agent: "coder", ...calls, calls: 1, failures: 1 }],
};

const emptySummary: DashboardSummary = {
  ...demoSummary,
  demo_data: false,
  projects: 0,
  runs: {
    total: 0,
    active: 0,
    completed: 0,
    partial: 0,
    failed: 0,
    cancelled: 0,
  },
  success_rate: null,
  avg_duration_seconds: null,
  cost_estimate_usd: null,
  approvals_pending: 0,
  recent_runs: [],
  metrics: {
    ...demoSummary.metrics,
    end_to_end_delivery_rate: null,
    first_pass_test_rate: null,
    repair_success_rate: null,
    human_intervention_count: 0,
    cost_per_successful_delivery: null,
  },
  providers: [],
  agents: [],
};

const RECIPES = {
  items: [
    {
      kind: "fastapi",
      project_type: "api",
      label: "API REST",
      description: "",
      deliverable: "code",
      outputs: [],
      phase: 1,
      available: true,
    },
    {
      kind: "excel",
      project_type: "excel",
      label: "Classeur Excel",
      description: "",
      deliverable: "non-code",
      outputs: [],
      phase: 1,
      available: true,
    },
  ],
};

function respondWith(status: number, body: unknown) {
  const fetchMock = vi.fn(async (url: string) =>
    String(url).endsWith("/recipes")
      ? new Response(JSON.stringify(RECIPES), { status: 200 })
      : new Response(JSON.stringify(body), { status }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderOverview() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <Overview />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("Overview", () => {
  it("shows real KPIs and labels demo data clearly", async () => {
    respondWith(200, demoSummary);
    renderOverview();

    expect(await screen.findByText("Données de démonstration")).toBeVisible();
    expect(
      screen.getByRole("group", { name: "Taux de réussite" }),
    ).toHaveTextContent("67");
    expect(
      screen.getByRole("group", { name: "Validations en attente" }),
    ).toHaveTextContent("1");
    expect(
      screen.getByRole("link", { name: "Rapport KPI hebdomadaire" }),
    ).toHaveAttribute("href", "/runs/run_demo_kpi");
    expect(screen.getByText("Échec")).toBeVisible();
  });

  it("shows unknown rates as unknown and explains the empty factory", async () => {
    respondWith(200, emptySummary);
    renderOverview();

    expect(await screen.findByText(/Aucun run pour l'instant/)).toBeVisible();
    expect(
      screen.getByRole("group", { name: "Taux de réussite" }),
    ).toHaveTextContent("—");
    expect(
      screen.queryByText("Données de démonstration"),
    ).not.toBeInTheDocument();
  });

  it("explains an API failure instead of showing fake numbers", async () => {
    respondWith(503, {
      error: {
        code: "unavailable",
        message: "Base indisponible.",
        details: null,
      },
    });
    renderOverview();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Base indisponible.",
    );
    expect(
      screen.queryByRole("group", { name: "Taux de réussite" }),
    ).not.toBeInTheDocument();
  });

  it("shows the factory metrics of §14.1, each with where it comes from", async () => {
    respondWith(200, demoSummary);
    renderOverview();

    const quality = within(
      await screen.findByRole("region", { name: "Qualité de l'usine" }),
    );
    expect(
      quality.getByRole("group", { name: "Livraison de bout en bout" }),
    ).toHaveTextContent("67");
    expect(
      quality.getByRole("group", { name: "Tests verts du premier coup" }),
    ).toHaveTextContent("33");
    expect(
      quality.getByRole("group", { name: "Réparations réussies" }),
    ).toHaveTextContent("50");
    expect(
      quality.getByRole("group", { name: "Interventions humaines" }),
    ).toHaveTextContent("1");
    expect(
      quality.getByRole("group", { name: "Délai jusqu'à l'aperçu" }),
    ).toHaveTextContent("Non mesuré");
    expect(
      quality.getByRole("group", { name: "Violations critiques" }),
    ).toHaveTextContent("0");
    expect(
      quality.getByText(/runs terminés dont l'état final est COMPLETED/),
    ).toBeInTheDocument();
  });

  it("lists every engine with its calls, latencies, failures and cost", async () => {
    respondWith(200, demoSummary);
    renderOverview();

    const table = await screen.findByRole("table", {
      name: "Moteurs et modèles",
    });
    const row = within(table).getByRole("row", { name: /anthropic/ });
    expect(row).toHaveTextContent("m1");
    expect(row).toHaveTextContent("2,0 s");
    expect(row).toHaveTextContent("2,9 s");
    expect(row).toHaveTextContent("partiel");
    expect(
      within(table).getByRole("row", { name: /openai/ }),
    ).toHaveTextContent("Non mesuré");
    expect(screen.getByRole("table", { name: "Agents" })).toHaveTextContent(
      "coder",
    );
  });

  it("asks the API again for the chosen period and project type", async () => {
    const fetchMock = respondWith(200, demoSummary);
    renderOverview();

    await userEvent.selectOptions(
      await screen.findByLabelText("Période"),
      "30",
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Type de projet"),
      "excel",
    );

    const urls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(urls).toContain("/api/v1/dashboard/summary?days=30");
    expect(urls).toContain(
      "/api/v1/dashboard/summary?days=30&project_type=excel",
    );
  });
});
