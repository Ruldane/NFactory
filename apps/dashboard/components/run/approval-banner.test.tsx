import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApprovalBanner } from "@/components/run/approval-banner";
import { runningRun } from "@/components/run/fixtures";
import type { Approval, RunDetail } from "@/lib/api/types";

const APPROVAL: Approval = {
  id: "apr_1",
  action_type: "provider_fallback",
  summary: "OpenAI : quota ou crédit épuisé : rechargez le compte ou relevez la limite de dépenses.",
  details: { role: "requirements", provider: "openai_api", model: "model-x", kind: "quota" },
  status: "pending",
  created_at: "2026-11-02T10:00:00Z",
};

const paused: RunDetail = { ...runningRun, state: "APPROVAL_PENDING", pending_approval: APPROVAL };

function serve() {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    const reply = (body: unknown) => new Response(JSON.stringify(body));
    if (path.endsWith("/approve")) return reply({ ...paused, state: "QUEUED", pending_approval: null });
    if (path.endsWith("/reject")) return reply({ ...paused, state: "FAILED", pending_approval: null });
    if (path.endsWith("/providers")) {
      return reply({
        providers: [
          { kind: "openai_api", label: "OpenAI", status: "connected", available: true },
          { kind: "ollama_local", label: "Ollama (local)", status: "connected", available: true },
        ],
      });
    }
    if (path.endsWith("/models")) {
      return reply({ models: [{ model_id: "llama-local", source: "discovered", pricing: null, context_window: null }] });
    }
    return reply(init ? {} : paused);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderBanner() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ApprovalBanner run={paused} approval={APPROVAL} />
    </QueryClientProvider>,
  );
}

const body = (fetchMock: ReturnType<typeof serve>, suffix: string) => {
  const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith(suffix));
  return call ? JSON.parse(String(call[1]?.body ?? "null")) : undefined;
};

afterEach(() => vi.unstubAllGlobals());

describe("ApprovalBanner", () => {
  it("says which engine failed and that nothing was switched", () => {
    serve();
    renderBanner();

    expect(screen.getByRole("alert")).toHaveTextContent("quota ou crédit épuisé");
    expect(screen.getByText(/Analyste des besoins/)).toBeVisible();
    expect(screen.getByText(/aucun autre moteur n'a été utilisé/)).toBeVisible();
  });

  it("retries the same engine", async () => {
    const fetchMock = serve();
    renderBanner();

    await userEvent.click(screen.getByRole("button", { name: "Réessayer le même moteur" }));

    await vi.waitFor(() => expect(body(fetchMock, "/approvals/apr_1/approve")).toEqual({}));
  });

  it("switches to the replacement the user picked", async () => {
    const fetchMock = serve();
    renderBanner();

    await screen.findByRole("option", { name: "Ollama (local)" }); // connected engines load
    await userEvent.selectOptions(screen.getByLabelText("Moteur de remplacement"), "ollama_local");
    await userEvent.type(screen.getByLabelText("Modèle de remplacement"), "llama-local");
    await userEvent.click(screen.getByRole("button", { name: "Reprendre avec ce moteur" }));

    await vi.waitFor(() =>
      expect(body(fetchMock, "/approvals/apr_1/approve")).toEqual({
        provider: "ollama_local",
        model: "llama-local",
      }),
    );
  });

  it("stops the run", async () => {
    const fetchMock = serve();
    renderBanner();

    await userEvent.click(screen.getByRole("button", { name: "Arrêter le run" }));

    await vi.waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/approvals/apr_1/reject"))).toBe(true),
    );
  });
});
