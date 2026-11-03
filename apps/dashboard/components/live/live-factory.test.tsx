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

const TRACE = {
  run_id: "run_busy",
  trace_id: "0123abcd456789ef0123abcd456789ef",
  cost_usd: 0.02,
  spans: [
    {
      id: "run_busy",
      parent_id: null,
      kind: "run",
      name: "run",
      start: "2026-11-01T10:00:00Z",
      end: null,
      duration_s: null,
      status: "running",
    },
    {
      id: "step_requirements",
      parent_id: "run_busy",
      kind: "step",
      name: "requirements",
      agent_role: "planner",
      start: "2026-11-01T10:00:00Z",
      end: "2026-11-01T10:00:05Z",
      duration_s: 5,
      status: "ok",
      calls: 1,
      cost_usd: 0.02,
    },
    {
      id: "evt_1",
      parent_id: "step_requirements",
      kind: "agent",
      name: "planner",
      start: "2026-11-01T10:00:01Z",
      end: "2026-11-01T10:00:04Z",
      duration_s: 3,
      status: "ok",
      provider: "anthropic",
      model: "m1",
      input_tokens: 100,
      output_tokens: 20,
      cost_usd: 0.02,
    },
    {
      id: "step_tests",
      parent_id: "run_busy",
      kind: "step",
      name: "tests",
      agent_role: "tester",
      start: "2026-11-01T10:00:05Z",
      end: "2026-11-01T10:00:12Z",
      duration_s: 7,
      status: "error",
      calls: 0,
      cost_usd: null,
    },
    {
      id: "evt_2",
      parent_id: "step_tests",
      kind: "check",
      name: "pytest",
      start: "2026-11-01T10:00:09Z",
      end: "2026-11-01T10:00:11Z",
      duration_s: 2.5,
      status: "error",
      exit_code: 1,
    },
  ],
};

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
            runs: {
              total: 2,
              active: 1,
              completed: 1,
              partial: 0,
              failed: 0,
              cancelled: 0,
            },
            success_rate: null,
            avg_duration_seconds: null,
            cost_estimate_usd: null,
            approvals_pending: 0,
            recent_runs: order.map(([id, title]) => recent(runs[id], title)),
          }),
        );
      }
      if (path.endsWith("/trace")) return new Response(JSON.stringify(TRACE));
      const id = path.split("/runs/")[1];
      return new Response(JSON.stringify(runs[id]));
    }),
  );
}

function renderLive() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
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

    expect(
      await screen.findByRole("radio", { name: /Classeur en cours/ }),
    ).toBeChecked();
    const graph = await screen.findByRole("list", {
      name: "Graphe des agents",
    });
    const tests = within(graph).getByRole("listitem", { name: /Tests/ });
    expect(tests).toHaveTextContent("Échec");
    expect(tests).toHaveTextContent("4 tentatives");
    // Retries are not repairs: only repair.started events count (none streamed here).
    expect(within(graph).getByText("↺ correction")).toBeVisible();
  });

  it("draws the run's trace with each call's model, tokens and cost", async () => {
    serve({ run_done: finished, run_busy: busy }, [
      ["run_done", "Classeur terminé"],
      ["run_busy", "Classeur en cours"],
    ]);
    renderLive();

    const trace = await screen.findByRole("list", { name: "Trace du run" });
    const call = within(trace).getByRole("listitem", { name: /planner/ });
    expect(call).toHaveTextContent("anthropic · m1");
    expect(call).toHaveTextContent("100 / 20 jetons");
    expect(call).toHaveTextContent("0,02");
    const check = within(trace).getByRole("listitem", { name: /pytest/ });
    expect(check).toHaveTextContent("code 1");
    expect(check).toHaveTextContent("Échec");
    expect(
      screen.getByText(/0123abcd456789ef0123abcd456789ef/),
    ).toBeInTheDocument();

    const graph = screen.getByRole("list", { name: "Graphe des agents" });
    expect(
      within(graph).getByRole("listitem", { name: /Besoins/ }),
    ).toHaveTextContent("1 appel · 0,02");
  });

  it("switches to another run", async () => {
    serve({ run_done: finished, run_busy: busy }, [
      ["run_done", "Classeur terminé"],
      ["run_busy", "Classeur en cours"],
    ]);
    renderLive();

    await userEvent.click(
      await screen.findByRole("radio", { name: /Classeur terminé/ }),
    );
    const graph = await screen.findByRole("list", {
      name: "Graphe des agents",
    });
    expect(
      within(graph).getByRole("listitem", { name: /Tests/ }),
    ).toHaveTextContent("Réussi");
  });

  it("says so when no run exists yet", async () => {
    serve({}, []);
    renderLive();

    expect(await screen.findByText(/Aucun run pour l'instant/)).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Lancer un projet" }),
    ).toHaveAttribute("href", "/new");
  });
});

describe("LiveLog", () => {
  const events: RunEvent[] = [
    {
      seq: 1,
      type: "step.started",
      step_id: null,
      created_at: "2026-11-01T10:00:00Z",
      payload: { step: "plan" },
    },
    {
      seq: 2,
      type: "agent.progress",
      step_id: null,
      created_at: "2026-11-01T10:00:01Z",
      payload: {
        agent: "planner",
        model: "fake-demo-1",
        trace_id: "abcdef0123456789",
      },
    },
    {
      seq: 3,
      type: "test.failed",
      step_id: null,
      created_at: "2026-11-01T10:00:02Z",
      payload: { failed: 1, total: 4 },
    },
  ];

  it("filters the log and shows the trace of agent calls", async () => {
    render(<LiveLog events={events} />);

    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByText(/trace abcdef01/)).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: /Erreurs/ }));
    expect(screen.getByRole("button", { name: /Erreurs/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(1);
    expect(items[0]).toHaveTextContent(/1/);
  });
});
