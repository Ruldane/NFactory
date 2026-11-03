import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Overview } from "@/components/overview/overview";
import type { DashboardSummary } from "@/lib/api/types";

const demoSummary: DashboardSummary = {
  demo_data: true,
  projects: 4,
  runs: { total: 4, active: 1, completed: 2, partial: 0, failed: 1, cancelled: 0 },
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
      steps: [{ name: "tests", agent_role: "tester", state: "FAILED", attempts: 4 }],
    },
  ],
};

const emptySummary: DashboardSummary = {
  ...demoSummary,
  demo_data: false,
  projects: 0,
  runs: { total: 0, active: 0, completed: 0, partial: 0, failed: 0, cancelled: 0 },
  success_rate: null,
  avg_duration_seconds: null,
  cost_estimate_usd: null,
  approvals_pending: 0,
  recent_runs: [],
};

function respondWith(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  );
}

function renderOverview() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
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
    expect(screen.getByRole("group", { name: "Taux de réussite" })).toHaveTextContent("67");
    expect(screen.getByRole("group", { name: "Validations en attente" })).toHaveTextContent("1");
    expect(screen.getByRole("link", { name: "Rapport KPI hebdomadaire" })).toHaveAttribute(
      "href",
      "/runs/run_demo_kpi",
    );
    expect(screen.getByText("Échec")).toBeVisible();
  });

  it("shows unknown rates as unknown and explains the empty factory", async () => {
    respondWith(200, emptySummary);
    renderOverview();

    expect(await screen.findByText(/Aucun run pour l'instant/)).toBeVisible();
    expect(screen.getByRole("group", { name: "Taux de réussite" })).toHaveTextContent("—");
    expect(screen.queryByText("Données de démonstration")).not.toBeInTheDocument();
  });

  it("explains an API failure instead of showing fake numbers", async () => {
    respondWith(503, { error: { code: "unavailable", message: "Base indisponible.", details: null } });
    renderOverview();

    expect(await screen.findByRole("alert")).toHaveTextContent("Base indisponible.");
    expect(screen.queryByRole("group", { name: "Taux de réussite" })).not.toBeInTheDocument();
  });
});
