import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SettingsView } from "@/components/settings/settings-view";
import type { WorkspaceSettings } from "@/lib/api/types";

const SETTINGS: WorkspaceSettings = {
  mode: "local",
  demo_mode: true,
  sandbox: "isolated",
  run_limits: { max_llm_calls: 80, max_agent_steps: 100, max_repair_attempts: 3 },
  limit_bounds: {
    max_llm_calls: { min: 1, max: 500 },
    max_agent_steps: { min: 20, max: 500 },
    max_repair_attempts: { min: 0, max: 10 },
  },
};

function serve(onPut: (body: unknown) => Response) {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.method === "PUT") return onPut(JSON.parse(String(init.body)));
    return new Response(JSON.stringify(SETTINGS));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderView() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SettingsView />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("SettingsView", () => {
  it("shows the environment honestly", async () => {
    serve(() => new Response("{}"));
    renderView();

    expect(await screen.findByText(/Sandbox isolé, sans Internet/)).toBeVisible();
    expect(screen.getByText(/Mode démo actif/)).toBeVisible();
    // Not built yet: shown with the phase that brings it.
    expect(screen.getByText(/Rétention et export des données/)).toBeVisible();
    expect(screen.getByText("Phase 6")).toBeVisible();
  });

  it("saves new run limits", async () => {
    const fetchMock = serve(
      (body) =>
        new Response(JSON.stringify({ ...SETTINGS, run_limits: body as WorkspaceSettings["run_limits"] })),
    );
    renderView();

    const calls = await screen.findByLabelText("Appels IA par run");
    expect(calls).toHaveValue(80);
    await userEvent.clear(calls);
    await userEvent.type(calls, "25");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer les limites" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Limites enregistrées");
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(put?.[0]).toBe("/api/v1/settings/run-limits");
    expect(JSON.parse(String(put?.[1]?.body))).toEqual({
      max_llm_calls: 25,
      max_agent_steps: 100,
      max_repair_attempts: 3,
    });
  });

  it("explains a refused value", async () => {
    serve(
      () =>
        new Response(
          JSON.stringify({ error: { code: "validation_error", message: "Requête invalide.", details: [] } }),
          { status: 422 },
        ),
    );
    renderView();

    await userEvent.click(await screen.findByRole("button", { name: "Enregistrer les limites" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Requête invalide.");
  });
});
