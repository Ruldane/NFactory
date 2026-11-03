import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProvidersView } from "@/components/providers/providers-view";
import type { ProviderView } from "@/lib/api/types";

const KEY = "sk-dashboard-test-0123456789abcdef";

const base = (kind: string, label: string, extra: Partial<ProviderView> = {}): ProviderView => ({
  kind,
  label,
  family: "api",
  phase: 2,
  available: true,
  status: "not_configured",
  needs_key: true,
  key_source: null,
  env_key: null,
  env_key_available: false,
  regions: [{ id: "global", label: "Mondial", needs_workspace: false }],
  region: null,
  workspace_id: null,
  custom_url: false,
  base_url: null,
  discovery: true,
  docs_url: "",
  last_checked_at: null,
  last_error: null,
  ...extra,
});

const PROVIDERS: ProviderView[] = [
  base("openai_api", "OpenAI", { env_key: "OPENAI_API_KEY" }),
  base("deepseek_api", "DeepSeek", {
    status: "invalid_credentials",
    key_source: "stored",
    last_error: { kind: "auth", message: "DeepSeek : clé refusée ou accès non autorisé." },
  }),
  base("qwen_api", "Alibaba Qwen", {
    discovery: false,
    regions: [
      { id: "eu-central-1", label: "Allemagne (Francfort) — espace dédié", needs_workspace: true },
      { id: "legacy-intl", label: "Singapour — domaine DashScope historique", needs_workspace: false },
    ],
  }),
  base("ollama_local", "Ollama (local)", {
    family: "local",
    needs_key: false,
    custom_url: true,
    regions: [],
    status: "connected",
    base_url: "http://127.0.0.1:11434",
  }),
  base("codex_local", "OpenAI Codex (local)", {
    family: "coding_agent",
    phase: 4,
    available: false,
    regions: [],
  }),
];

type Handler = (url: string, init?: RequestInit) => Response | undefined;

function serve(handler: Handler = () => undefined) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    const custom = handler(path, init);
    if (custom) return custom;
    const reply = (body: unknown) => new Response(JSON.stringify(body));
    if (path.endsWith("/providers")) return reply({ providers: PROVIDERS });
    if (path.endsWith("/local-runtimes")) {
      return reply({
        bridge: { status: "unreachable", message: "Pont local non joignable : lancez ./scripts/bridge.ps1.", version: null },
        runtimes: [],
      });
    }
    if (path.endsWith("/models")) return reply({ models: [] });
    if (path.endsWith("/routing")) {
      return reply({
        routing: { default: null, roles: {}, fallback: "ask_user", local_only: false },
        roles: [{ id: "requirements", label: "Analyste des besoins" }],
      });
    }
    return reply({});
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderView() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ProvidersView />
    </QueryClientProvider>,
  );
}

const card = async (label: string) =>
  within(await screen.findByRole("region", { name: label }));

afterEach(() => vi.unstubAllGlobals());

describe("ProvidersView", () => {
  it("shows every provider with an honest status, glyph and label", async () => {
    serve();
    renderView();

    expect((await card("OpenAI")).getByText("Non configuré")).toBeVisible();
    expect((await card("Ollama (local)")).getByText("Connecté")).toBeVisible();
    const deepseek = await card("DeepSeek");
    expect(deepseek.getByText("Clé refusée")).toBeVisible();
    expect(deepseek.getByText(/clé refusée ou accès non autorisé/)).toBeVisible();
  });

  it("shows the local tools through the bridge, not as API providers", async () => {
    serve();
    renderView();

    expect(await screen.findByRole("heading", { name: "Outils locaux" })).toBeVisible();
    expect(await screen.findByText("Pont arrêté")).toBeVisible();
    expect(screen.queryByRole("region", { name: "OpenAI Codex (local)" })).toBeNull();
  });

  it("saves a key without ever showing it back", async () => {
    const fetchMock = serve((path, init) =>
      path.endsWith("/openai_api/configuration") && init?.method === "PUT"
        ? new Response(JSON.stringify({ ...PROVIDERS[0], status: "configured", key_source: "stored" }))
        : undefined,
    );
    renderView();
    const openai = await card("OpenAI");

    const input = openai.getByLabelText("Clé API");
    expect(input).toHaveAttribute("type", "password");
    await userEvent.type(input, KEY);
    await userEvent.click(openai.getByRole("button", { name: "Enregistrer" }));

    expect(await openai.findByRole("status")).toHaveTextContent("Configuration enregistrée");
    expect(input).toHaveValue("");
    expect(document.body.innerHTML).not.toContain(KEY);
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(String(put?.[1]?.body))).toMatchObject({ api_key: KEY, region: "global" });
  });

  it("runs the consented connection test and shows its result", async () => {
    const fetchMock = serve((path, init) =>
      path.endsWith("/ollama_local/validate") && init?.method === "POST"
        ? new Response(
            JSON.stringify({
              ok: true,
              status: "connected",
              message: "Ollama (local) : connexion réussie, 3 modèle(s) trouvé(s).",
              latency_ms: 12,
              models_found: 3,
            }),
          )
        : undefined,
    );
    renderView();
    const ollama = await card("Ollama (local)");

    await userEvent.click(ollama.getByRole("button", { name: "Tester la connexion" }));

    expect(await ollama.findByRole("status")).toHaveTextContent("3 modèle(s) trouvé(s)");
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/ollama_local/validate"))).toBe(
      true,
    );
  });

  it("asks Qwen for its workspace id and explains a catalog-only provider", async () => {
    serve();
    renderView();
    const qwen = await card("Alibaba Qwen");

    expect(qwen.getByLabelText("Identifiant d'espace de travail")).toBeVisible();
    expect(qwen.getByLabelText("Région")).toBeVisible();
    expect(qwen.getByText(/ne publie pas sa liste de modèles/)).toBeVisible();
  });

  it("shows the base URL field for a local engine and no key field", async () => {
    serve();
    renderView();
    const ollama = await card("Ollama (local)");

    expect(ollama.getByLabelText("URL de base")).toHaveValue("http://127.0.0.1:11434");
    expect(ollama.queryByLabelText("Clé API")).toBeNull();
  });
});
