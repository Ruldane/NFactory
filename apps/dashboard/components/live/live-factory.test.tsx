import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LiveFactory } from "@/components/live/live-factory";
import { LiveLog } from "@/components/live/live-log";
import { completedRun, runningRun } from "@/components/run/fixtures";
import type { RunDetail, RunEvent } from "@/lib/api/types";

const recent = (run: RunDetail, title: string) => ({
  id: run.id,
  project_id: run.project.id,
  project_title: title,
  state: run.state,
  is_demo: false,
  created_at: run.created_at,
  finished_at: run.finished_at,
  steps: [],
});

function serve(runs: Record<string, RunDetail>, order: [string, string][]) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const path = String(url);
      if (path.endsWith("/dashboard/summary")) {
        return new Response(
          JSON.stringify({
            demo_data: false,
            projects: 1,
            runs: { total: 2, active: 1, completed: 1, partial: 0, failed: 0, cancelled: 0 },
            success_rate: null,
            avg_duration_seconds: null,
            cost_estimate_usd: null,
            approvals_pending: 0,
            recent_runs: order.map(([id, title]) => recent(runs[id], title)),
          }),
        );
      }
      const id = path.split("/runs/")[1];
      return new Response(JSON.stringify(runs[id]));
    }),
  );
}

function renderLive() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <LiveFactory />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("LiveFactory", () => {
  const finished = { ...completedRun, id: "run_done" };
  const busy = { ...runningRun, id: "run_busy" };

  it("follows the run in progress and draws its agent graph", async () => {
    serve({ run_done: finished, run_busy: busy }, [
      ["run_done", "Classeur terminé"],
      ["run_busy", "Classeur en cours"],
    ]);
    renderLive();

    expect(await screen.findByRole("radio", { name: /Classeur en cours/ })).toBeChecked();
    const graph = await screen.findByRole("list", { name: "Graphe des agents" });
    const tests = within(graph).getByRole("listitem", { name: /Tests/ });
    expect(tests).toHaveTextContent("Échec");
    expect(tests).toHaveTextContent("4 tentatives");
    // Retries are not repairs: only repair.started events count (none streamed here).
    expect(within(graph).getByText("↺ correction")).toBeVisible();
  });

  it("switches to another run", async () => {
    serve({ run_done: finished, run_busy: busy }, [
      ["run_done", "Classeur terminé"],
      ["run_busy", "Classeur en cours"],
    ]);
    renderLive();

    await userEvent.click(await screen.findByRole("radio", { name: /Classeur terminé/ }));
    const graph = await screen.findByRole("list", { name: "Graphe des agents" });
    expect(within(graph).getByRole("listitem", { name: /Tests/ })).toHaveTextContent("Réussi");
  });

  it("says so when no run exists yet", async () => {
    serve({}, []);
    renderLive();

    expect(await screen.findByText(/Aucun run pour l'instant/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Lancer un projet" })).toHaveAttribute("href", "/new");
  });
});

describe("LiveLog", () => {
  const events: RunEvent[] = [
    { seq: 1, type: "step.started", step_id: null, created_at: "2026-11-01T10:00:00Z", payload: { step: "plan" } },
    {
      seq: 2,
      type: "agent.progress",
      step_id: null,
      created_at: "2026-11-01T10:00:01Z",
      payload: { agent: "planner", model: "fake-demo-1", trace_id: "abcdef0123456789" },
    },
    { seq: 3, type: "test.failed", step_id: null, created_at: "2026-11-01T10:00:02Z", payload: { failed: 1, total: 4 } },
  ];

  it("filters the log and shows the trace of agent calls", async () => {
    render(<LiveLog events={events} />);

    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByText(/trace abcdef01/)).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: /Erreurs/ }));
    expect(screen.getByRole("button", { name: /Erreurs/ })).toHaveAttribute("aria-pressed", "true");
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(1);
    expect(items[0]).toHaveTextContent(/1/);
  });
});
