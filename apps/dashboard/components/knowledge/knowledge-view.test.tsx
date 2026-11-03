import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeView } from "@/components/knowledge/knowledge-view";
import type { KnowledgeDocument, KnowledgeSearch, KnowledgeSettings } from "@/lib/api/types";

const DOC: KnowledgeDocument = {
  id: "doc_1",
  path: "procedures/licences.md",
  project_id: null,
  kind: "markdown",
  size_bytes: 120,
  revision: "1",
  chunks: 4,
  embedded: 1,
  created_at: "2026-11-02T10:00:00Z",
};

const SETTINGS: KnowledgeSettings = {
  embedding: { provider: "local", model: "empreinte-v1" },
  index: { total: 4, embedded: 1 },
  options: [
    { provider: "local", label: "Empreinte locale (sans modèle)", local: true, available: true, reason: null },
    {
      provider: "openai_api",
      label: "OpenAI",
      local: false,
      available: false,
      reason: "OpenAI n'est pas connecté : testez sa connexion dans Moteurs IA.",
    },
    { provider: "ollama_local", label: "Ollama (local)", local: true, available: true, reason: null },
  ],
  index_error: null,
};

const SEARCH: KnowledgeSearch = {
  hits: [
    {
      chunk_id: "chk_1",
      document_id: "doc_1",
      path: "procedures/licences.md",
      content: "Renouveler chaque licence 30 jours avant.",
      start_line: 3,
      end_line: 5,
      section: "Licences",
      symbol: null,
      page: null,
      score: 0.03,
      matched: ["text", "vector"],
    },
  ],
  engine: { key: "local:empreinte-v1", used: true, error: null },
};

function serve(settings: KnowledgeSettings = SETTINGS) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
    if (path.includes("/knowledge/search")) return reply(SEARCH);
    if (path.includes("/knowledge/settings")) {
      if (init?.method === "PUT") return reply(settings);
      return reply(settings);
    }
    if (path.includes("/knowledge/documents") && init?.method === "POST") {
      return reply({ ...DOC, id: "doc_2", path: "achats.md", duplicate: false, replaced: false }, 201);
    }
    if (path.includes("/knowledge/documents")) return reply({ items: [DOC] });
    if (path.includes("/projects")) {
      return reply({ items: [{ id: "proj_1", title: "Licences IT", type: "webapp" }], next_cursor: null });
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
      <KnowledgeView />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("KnowledgeView", () => {
  it("lists documents with an honest index status", async () => {
    serve();
    renderView();

    const row = (await screen.findByText("procedures/licences.md")).closest("li")!;
    expect(within(row).getByText("Vecteurs en cours")).toBeVisible();
    expect(within(row).getByText(/recherche plein texte prête/)).toBeVisible();
  });

  it("uploads a file, optionally into a project", async () => {
    const fetchMock = serve();
    renderView();

    await screen.findByRole("option", { name: "Licences IT" });
    await userEvent.selectOptions(screen.getByLabelText("Portée"), "proj_1");
    const file = new File(["# Achats"], "achats.md", { type: "text/markdown" });
    await userEvent.upload(screen.getByLabelText("Fichier à importer"), file);
    await userEvent.click(screen.getByRole("button", { name: "Importer" }));

    expect(await screen.findByRole("status")).toHaveTextContent("achats.md importé");
    const call = fetchMock.mock.calls.find(([, init]) => init?.method === "POST")!;
    const form = call[1]!.body as FormData;
    expect((form.get("file") as File).name).toBe("achats.md");
    expect(form.get("project_id")).toBe("proj_1");
  });

  it("finds passages and links each citation to its source lines", async () => {
    serve();
    renderView();

    await userEvent.type(screen.getByLabelText("Rechercher dans la base"), "renouveler licence");
    await userEvent.click(screen.getByRole("button", { name: "Rechercher" }));

    const link = await screen.findByRole("link", { name: /procedures\/licences\.md · lignes 3 à 5/ });
    expect(link).toHaveAttribute("href", "/knowledge/documents/doc_1?lignes=3-5#L3");
    expect(screen.getByText("Renouveler chaque licence 30 jours avant.")).toBeVisible();
    expect(screen.getByText(/plein texte \+ vecteurs/)).toBeVisible();
  });

  it("offers only usable embedding engines and says why the others are not", async () => {
    serve();
    renderView();

    const openai = await screen.findByRole("option", { name: /OpenAI/ });
    expect(openai).toBeDisabled();
    expect(screen.getByText(/OpenAI n'est pas connecté/)).toBeVisible();
    expect(screen.getByText("1 / 4 passages vectorisés")).toBeVisible();
  });

  it("shows why indexing stopped", async () => {
    serve({ ...SETTINGS, index_error: "OpenAI : clé refusée." });
    renderView();

    expect(await screen.findByRole("alert")).toHaveTextContent("OpenAI : clé refusée.");
  });
});
