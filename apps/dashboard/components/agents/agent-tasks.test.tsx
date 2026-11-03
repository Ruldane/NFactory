import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentTasks } from "@/components/agents/agent-tasks";
import type { AgentTask } from "@/lib/api/types";

const RUNNING: AgentTask = {
  id: "t_0123456789ab",
  runtime: "codex",
  repo_id: "nfactory-test",
  branch: "nfactory/nfactory-test/t_0123456789ab",
  base: "3eff134",
  status: "running",
  events: [{ type: "started" }],
  manifest: [],
  diff: "",
  diff_truncated: false,
  error: "",
  created_at: 1_800_000_000,
};

const DONE: AgentTask = {
  ...RUNNING,
  status: "succeeded",
  events: [
    { type: "started" },
    { type: "command", command: "python -m pytest", status: "failed", exit_code: 1 },
    { type: "file_change", changes: [{ path: "calc.py", kind: "update" }] },
    { type: "message", text: "Ajout de multiply(a, b)." },
    { type: "completed", usage: { input_tokens: 1200, output_tokens: 45 } },
  ],
  manifest: [{ path: "calc.py", change: "modified" }],
  diff: "--- a/calc.py\n+++ b/calc.py\n@@ -1 +1,2 @@\n-x = 1\n+def multiply(a, b):\n+    return a * b\n",
};

type Handler = (path: string, init?: RequestInit) => Response | undefined;

function serve(handler: Handler) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const response = handler(String(url), init);
    if (response) return response;
    return new Response(JSON.stringify({ error: { code: "not_found", message: "?" } }), { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const repos = () => json({ repos: [{ id: "nfactory-test", name: "nfactory-test" }] });

function renderTasks() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AgentTasks pollMs={10} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("AgentTasks", () => {
  it("sends the user to pair the bridge first", async () => {
    serve((path) =>
      path.endsWith("/local-runtimes/repos")
        ? json({ error: { code: "bridge_unpaired", message: "Associez d'abord le pont local (page Moteurs IA)." } }, 409)
        : undefined,
    );
    renderTasks();

    expect(await screen.findByText(/Associez d'abord le pont local/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Moteurs IA" })).toHaveAttribute("href", "/providers");
  });

  it("explains how to authorize a repository when there is none", async () => {
    serve((path) => (path.endsWith("/local-runtimes/repos") ? json({ repos: [] }) : undefined));
    renderTasks();

    expect(await screen.findByText(/bridge\.ps1 -Allow/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Lancer Codex" })).toBeNull();
  });

  it("starts Codex only once the user has agreed", async () => {
    let polls = 0;
    const fetchMock = serve((path, init) => {
      if (path.endsWith("/local-runtimes/repos")) return repos();
      if (path.endsWith("/local-runtimes/tasks") && init?.method === "POST") return json(RUNNING, 202);
      if (path.endsWith(`/tasks/${RUNNING.id}`)) return json(++polls < 2 ? RUNNING : DONE);
      return undefined;
    });
    renderTasks();

    const launch = await screen.findByRole("button", { name: "Lancer Codex" });
    await userEvent.type(screen.getByLabelText("Tâche pour l'agent"), "Ajoute multiply");
    expect(launch).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: /J'autorise Codex/ }));
    await userEvent.click(launch);

    const started = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith("/tasks") && init?.method === "POST");
    expect(JSON.parse(String(started?.[1]?.body))).toEqual({
      runtime: "codex",
      repo_id: "nfactory-test",
      task: "Ajoute multiply",
      consent: true,
    });
    expect(await screen.findByText("Terminée avec des changements")).toBeVisible();
  });

  it("shows the events, the changed files and the diff of a finished task", async () => {
    serve((path, init) => {
      if (path.endsWith("/local-runtimes/repos")) return repos();
      if (path.endsWith("/local-runtimes/tasks") && init?.method === "POST") return json(DONE, 202);
      if (path.endsWith(`/tasks/${DONE.id}`)) return json(DONE);
      return undefined;
    });
    renderTasks();
    await userEvent.type(await screen.findByLabelText("Tâche pour l'agent"), "Ajoute multiply");
    await userEvent.click(screen.getByRole("checkbox", { name: /J'autorise Codex/ }));
    await userEvent.click(screen.getByRole("button", { name: "Lancer Codex" }));

    const events = within(await screen.findByRole("list", { name: "Événements de l'agent" }));
    expect(events.getByText("python -m pytest")).toBeVisible();
    expect(events.getByText("code 1")).toBeVisible();
    expect(events.getByText("Ajout de multiply(a, b).")).toBeVisible();
    const files = within(screen.getByRole("list", { name: "Fichiers changés" }));
    expect(files.getByText("calc.py")).toBeVisible();
    expect(files.getByText("modifié")).toBeVisible();
    expect(screen.getByText("+def multiply(a, b):")).toBeVisible();
    expect(screen.getByText(DONE.branch)).toBeVisible();
  });

  it("says honestly when Codex needs a login, with the official command", async () => {
    serve((path, init) => {
      if (path.endsWith("/local-runtimes/repos")) return repos();
      if (path.endsWith("/local-runtimes/tasks") && init?.method === "POST") {
        return json(
          { error: { code: "needs_login", message: "Codex n'est pas connecté : lancez « codex login » dans un terminal." } },
          409,
        );
      }
      return undefined;
    });
    renderTasks();
    await userEvent.type(await screen.findByLabelText("Tâche pour l'agent"), "x");
    await userEvent.click(screen.getByRole("checkbox", { name: /J'autorise Codex/ }));
    await userEvent.click(screen.getByRole("button", { name: "Lancer Codex" }));

    const alert = within(await screen.findByRole("alert"));
    expect(alert.getByText("Connexion requise")).toBeVisible();
    expect(alert.getByText("codex login")).toBeVisible();
    expect(alert.getByRole("link", { name: "Moteurs IA" })).toHaveAttribute("href", "/providers");
  });

  it("can discard a finished task", async () => {
    const fetchMock = serve((path, init) => {
      if (path.endsWith("/local-runtimes/repos")) return repos();
      if (path.endsWith("/local-runtimes/tasks") && init?.method === "POST") return json(DONE, 202);
      if (path.endsWith("/discard")) return json({ ...DONE, status: "discarded", diff: "" });
      if (path.endsWith(`/tasks/${DONE.id}`)) return json(DONE);
      return undefined;
    });
    renderTasks();
    await userEvent.type(await screen.findByLabelText("Tâche pour l'agent"), "x");
    await userEvent.click(screen.getByRole("checkbox", { name: /J'autorise Codex/ }));
    await userEvent.click(screen.getByRole("button", { name: "Lancer Codex" }));

    await userEvent.click(await screen.findByRole("button", { name: "Abandonner les changements" }));

    expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith("/discard") && init?.method === "POST")).toBe(true);
    expect(await screen.findByText("Abandonnée")).toBeVisible();
  });

  it("prepares a Claude Code handoff, says how to run it, then imports the changes", async () => {
    const waiting: AgentTask = { ...RUNNING, runtime: "claude", status: "awaiting_user", events: [] };
    const fetchMock = serve((path, init) => {
      if (path.endsWith("/local-runtimes/repos")) return repos();
      if (path.endsWith("/local-runtimes/tasks") && init?.method === "POST") return json(waiting, 202);
      if (path.endsWith("/collect")) return json({ ...DONE, runtime: "claude" });
      if (path.endsWith(`/tasks/${RUNNING.id}`)) return json(waiting);
      return undefined;
    });
    renderTasks();

    await userEvent.click(await screen.findByRole("radio", { name: /Claude Code/ }));
    await userEvent.type(screen.getByLabelText("Tâche pour l'agent"), "Ajoute divide");
    const prepare = screen.getByRole("button", { name: "Préparer le relais" });
    expect(prepare).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: /Je lancerai Claude Code moi-même/ }));
    await userEvent.click(prepare);

    const started = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith("/tasks") && init?.method === "POST");
    expect(JSON.parse(String(started?.[1]?.body))).toMatchObject({ runtime: "claude", consent: true });
    expect(await screen.findByText("En attente de vous")).toBeVisible();
    expect(screen.getByText(`./scripts/bridge.ps1 -Handoff ${RUNNING.id}`)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Importer les changements" }));

    expect(await screen.findByText("+def multiply(a, b):")).toBeVisible();
  });

  it("tests a finished change in the sandbox and shows the verdict", async () => {
    const check = {
      id: "agc_0123",
      task_id: DONE.id,
      repo_id: DONE.repo_id,
      runtime: "codex",
      status: "queued",
      report: null,
      error: "",
      created_at: "2026-11-03T06:00:00Z",
      finished_at: null,
    };
    const passed = {
      ...check,
      status: "failed",
      report: {
        command: "python -m pytest -q",
        passed: 9,
        failed: 1,
        errors: 0,
        skipped: 0,
        failures: [{ name: "tests.test_calc::test_divide_by_zero", message: "assert False" }],
        output_tail: "1 failed, 9 passed",
      },
      finished_at: "2026-11-03T06:00:05Z",
    };
    let reads = 0;
    const fetchMock = serve((path, init) => {
      if (path.endsWith("/local-runtimes/repos")) return repos();
      if (path.endsWith("/local-runtimes/tasks") && init?.method === "POST") return json(DONE, 202);
      if (path.endsWith(`/tasks/${DONE.id}/checks`) && init?.method === "POST") return json(check, 202);
      if (path.endsWith("/checks/agc_0123")) return json(++reads < 2 ? check : passed);
      if (path.endsWith(`/tasks/${DONE.id}`)) return json(DONE);
      return undefined;
    });
    renderTasks();
    await userEvent.type(await screen.findByLabelText("Tâche pour l'agent"), "x");
    await userEvent.click(screen.getByRole("checkbox", { name: /J'autorise Codex/ }));
    await userEvent.click(screen.getByRole("button", { name: "Lancer Codex" }));

    await userEvent.click(await screen.findByRole("button", { name: "Tester dans le sandbox" }));

    const verdict = within(await screen.findByRole("region", { name: "Test dans le sandbox" }));
    expect(await verdict.findByText("Tests en échec")).toBeVisible();
    expect(verdict.getByText("9 réussis · 1 en échec")).toBeVisible();
    expect(verdict.getByText("tests.test_calc::test_divide_by_zero")).toBeVisible();
    expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith("/checks") && init?.method === "POST")).toBe(true);
  });
});
