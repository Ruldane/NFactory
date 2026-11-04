import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RoutingEditor } from "@/components/providers/routing-editor";
import type { ProviderView, RoutingView } from "@/lib/api/types";

const provider = (kind: string, label: string, status: string, family = "api"): ProviderView =>
  ({ kind, label, status, family, available: family !== "coding_agent" }) as ProviderView;

const PROVIDERS = [
  provider("openai_api", "OpenAI", "connected"),
  provider("deepseek_api", "DeepSeek", "configured"),
  provider("ollama_local", "Ollama (local)", "connected", "local"),
];

const VIEW: RoutingView = {
  routing: { default: null, roles: {}, fallback: "ask_user", local_only: false, eu_only: false },
  roles: [
    { id: "requirements", label: "Analyste des besoins" },
    { id: "reviewer", label: "Relecteur" },
  ],
};

function serve(onPut: (body: unknown) => Response) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    if (init?.method === "PUT") return onPut(JSON.parse(String(init.body)));
    if (path.endsWith("/openai_api/models")) {
      return new Response(
        JSON.stringify({ models: [{ model_id: "model-x", source: "discovered", pricing: null, context_window: null }] }),
      );
    }
    if (path.endsWith("/models")) return new Response(JSON.stringify({ models: [] }));
    return new Response(JSON.stringify(VIEW));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderEditor() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RoutingEditor providers={PROVIDERS} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("RoutingEditor", () => {
  it("offers only connected engines", async () => {
    serve(() => new Response("{}"));
    renderEditor();

    const select = await screen.findByLabelText("Fournisseur par défaut");
    const options = [...(select as HTMLSelectElement).options].map((o) => o.textContent);
    expect(options).toEqual(["Aucun", "OpenAI", "Ollama (local)"]);
  });

  it("saves the default engine, a role override and the fallback rule", async () => {
    const fetchMock = serve((body) => new Response(JSON.stringify({ ...VIEW, routing: body })));
    renderEditor();

    await userEvent.selectOptions(await screen.findByLabelText("Fournisseur par défaut"), "openai_api");
    await userEvent.type(screen.getByLabelText("Modèle par défaut"), "model-x");
    await userEvent.selectOptions(screen.getByLabelText("Fournisseur — Relecteur"), "ollama_local");
    await userEvent.type(screen.getByLabelText("Modèle — Relecteur"), "llama-local");
    await userEvent.click(screen.getByLabelText(/Arrêter le run en échec/));
    await userEvent.click(screen.getByLabelText(/Local uniquement/));
    await userEvent.click(screen.getByLabelText(/UE ou local uniquement/));
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer le routage" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Routage enregistré");
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(put?.[0]).toBe("/api/v1/routing");
    expect(JSON.parse(String(put?.[1]?.body))).toEqual({
      default: { provider: "openai_api", model: "model-x" },
      roles: { reviewer: { provider: "ollama_local", model: "llama-local" } },
      fallback: "none",
      local_only: true,
      eu_only: true,
    });
  });

  it("explains that no engine is ever switched without the user", async () => {
    serve(() => new Response("{}"));
    renderEditor();

    expect(await screen.findByText(/jamais remplacé sans votre accord/)).toBeVisible();
  });
});
