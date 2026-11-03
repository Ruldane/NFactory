import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { artifacts, completedRun, runningRun } from "@/components/run/fixtures";
import { RunView } from "@/components/run/run-view";
import type { RunDetail } from "@/lib/api/types";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

function serve(run: RunDetail, onCancel?: () => RunDetail) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    const reply = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), { status });
    if (path.endsWith("/cancel") && init?.method === "POST") return reply(onCancel?.() ?? run);
    if (path.endsWith("/artifacts")) return reply({ items: run.state === "COMPLETED" ? artifacts : [] });
    if (path.endsWith("/files")) return reply({ files: ["EXPLICATION.md", "build_report.py"] });
    if (path.includes("/files/content")) {
      return reply({ path: "EXPLICATION.md", content: "# Explication\nCe classeur…", binary: false, size: 30 });
    }
    return reply(run);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderView() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RunView runId="run_1" />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("RunView", () => {
  it("shows the run, marks the demo model and lets the user cancel", async () => {
    const fetchMock = serve(runningRun, () => ({ ...runningRun, state: "CANCELLED" }));
    renderView();

    expect(await screen.findByRole("heading", { name: "Rapport des heures" })).toBeVisible();
    expect(screen.getByText("En cours")).toBeVisible();
    expect(screen.getByText(/Modèle démo/)).toBeVisible();
    // Short trace id to follow the run in logs; the budget of agent calls.
    expect(screen.getByText(/trace 0123abcd/)).toBeVisible();
    expect(screen.getByText(/80 appels IA max/)).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "Annuler le run" }));

    await vi.waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/runs/run_1/cancel",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    expect(await screen.findByText("Annulé")).toBeVisible();
  });

  it("names the engines of a routed run", async () => {
    serve({
      ...runningRun,
      model: null,
      engines: {
        requirements: { provider: "openai_api", model: "model-x" },
        reviewer: { provider: "ollama_local", model: "llama-local" },
      },
    });
    renderView();

    expect(await screen.findByText(/moteurs openai_api · model-x, ollama_local · llama-local/)).toBeVisible();
    expect(screen.queryByText(/Modèle démo/)).toBeNull();
  });

  it("shows the decision a paused run waits for", async () => {
    serve({
      ...runningRun,
      state: "APPROVAL_PENDING",
      pending_approval: {
        id: "apr_1",
        action_type: "provider_fallback",
        summary: "OpenAI : quota ou crédit épuisé.",
        details: { role: "requirements", provider: "openai_api", model: "model-x", kind: "quota" },
        status: "pending",
        created_at: "2026-11-02T10:00:00Z",
      },
    });
    renderView();

    expect(await screen.findByRole("button", { name: "Réessayer le même moteur" })).toBeVisible();
    expect(screen.getByText("OpenAI : quota ou crédit épuisé.")).toBeVisible();
  });

  it("offers deliverables once finished, without a cancel button", async () => {
    serve(completedRun);
    renderView();

    expect(await screen.findByRole("link", { name: /rapport-des-heures\.xlsx/ })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Annuler le run" })).not.toBeInTheDocument();
  });

  it("shows the explanation written for the user", async () => {
    serve(completedRun);
    renderView();

    await userEvent.click(await screen.findByRole("tab", { name: "Explication" }));
    expect(await screen.findByText("Ce classeur calcule les heures par équipe.")).toBeVisible();
    // Real sections and lists, not raw Markdown.
    expect(screen.getByRole("heading", { name: "À vérifier avant utilisation" })).toBeVisible();
    const produced = screen.getByRole("list", { name: "Ce qui a été produit" });
    expect(within(produced).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("Aucune limite signalée.")).toBeVisible();
    expect(screen.queryByText(/^#/)).not.toBeInTheDocument();
  });

  it("lists the sources the run cited, each linked to its lines", async () => {
    const steps = completedRun.steps.map((step) =>
      step.name === "requirements"
        ? {
            ...step,
            output: {
              sources: [
                {
                  id: "S1",
                  document_id: "doc_1",
                  path: "procedures/licences.md",
                  start_line: 3,
                  end_line: 5,
                  section: "Licences",
                },
              ],
            },
          }
        : step,
    );
    serve({ ...completedRun, steps });
    renderView();

    await userEvent.click(await screen.findByRole("tab", { name: "Sources" }));
    const link = await screen.findByRole("link", { name: /procedures\/licences\.md · lignes 3 à 5/ });
    expect(link).toHaveAttribute("href", "/knowledge/documents/doc_1?lignes=3-5#L3");
    expect(screen.getByText("S1")).toBeVisible();
  });

  it("says when a run had no knowledge base to search", async () => {
    serve(completedRun);
    renderView();

    await userEvent.click(await screen.findByRole("tab", { name: "Sources" }));
    expect(await screen.findByText(/aucun document dans la base de connaissances/)).toBeVisible();
  });

  it("waits for the documentation step before explaining", async () => {
    serve(runningRun);
    renderView();

    await userEvent.click(await screen.findByRole("tab", { name: "Explication" }));
    expect(await screen.findByText(/rédigée à l'étape Documentation/)).toBeVisible();
  });

  it("explains an unknown run", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ error: { code: "not_found", message: "Run introuvable.", details: null } }),
            { status: 404 },
          ),
      ),
    );
    renderView();

    expect(await screen.findByRole("alert")).toHaveTextContent("Run introuvable.");
  });
});

describe("RunView preview tab", () => {
  it("offers a live preview only when the deliverable has one", async () => {
    const webapp: RunDetail = {
      ...completedRun,
      steps: completedRun.steps.map((s) =>
        s.name === "package" ? { ...s, output: { preview: { argv: ["python", "tools/preview.py"], port: 8000 } } } : s,
      ),
    };
    serve(webapp);
    renderView();

    expect(await screen.findByRole("tab", { name: "Aperçu" })).toBeVisible();
  });

  it("has no preview tab for a workbook", async () => {
    serve(completedRun);
    renderView();

    expect(await screen.findByRole("tab", { name: "Livrables" })).toBeVisible();
    expect(screen.queryByRole("tab", { name: "Aperçu" })).toBeNull();
  });
});

describe("RunView change requests", () => {
  it("offers a change request once the run is delivered", async () => {
    serve(completedRun);
    renderView();

    expect(await screen.findByLabelText("Évolution demandée")).toBeVisible();
  });

  it("has no change request while the run is running", async () => {
    serve(runningRun);
    renderView();

    await screen.findByRole("heading", { name: "Rapport des heures" });
    expect(screen.queryByLabelText("Évolution demandée")).toBeNull();
  });

  it("links a child run to its parent and shows its changes", async () => {
    const childRun: RunDetail = {
      ...completedRun,
      parent_run_id: "run_parent",
      steps: completedRun.steps.map((s) =>
        s.name === "package"
          ? { ...s, output: { changes: { parent_run_id: "run_parent", added: [], modified: ["app/models.py"], removed: [], truncated: false } } }
          : s,
      ),
    };
    serve(childRun);
    renderView();

    expect(await screen.findByText(/Évolution du run/)).toHaveTextContent("Évolution du run run_parent");
    await userEvent.click(screen.getByRole("tab", { name: "Modifications" }));
    expect(await screen.findByText("app/models.py")).toBeVisible();
  });
});
