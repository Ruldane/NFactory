import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LocalTools } from "@/components/providers/local-tools";
import type { LocalRuntimesView } from "@/lib/api/types";

const PAIRED: LocalRuntimesView = {
  bridge: { status: "paired", message: "Pont local associé.", version: "0.1.0" },
  runtimes: [
    {
      kind: "codex",
      label: "OpenAI Codex CLI",
      status: "connected",
      version: "0.155.1",
      login: "chatgpt",
      login_command: "codex login",
      modes: { runtime: "available" },
      detail: "",
    },
    {
      kind: "claude",
      label: "Claude Code",
      status: "needs_login",
      version: "2.1.316",
      login: null,
      login_command: "claude auth login",
      modes: { handoff: "available", runtime: "blocked_by_policy" },
      detail: "",
    },
    {
      kind: "gh",
      label: "GitHub CLI",
      status: "not_installed",
      version: null,
      login: null,
      login_command: "gh auth login",
      modes: {},
      detail: "« gh » introuvable dans le PATH.",
    },
  ],
};

const state = (status: LocalRuntimesView["bridge"]["status"], message: string) => ({
  bridge: { status, message, version: null },
  runtimes: [],
});

function serve(first: LocalRuntimesView, handler?: (path: string, init?: RequestInit) => Response | undefined) {
  let current = first;
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    const custom = handler?.(path, init);
    if (custom) return custom;
    if (path.endsWith("/local-runtimes/pairing") && init?.method === "POST") current = PAIRED;
    if (path.endsWith("/local-runtimes/pairing") && init?.method === "DELETE") {
      current = state("unpaired", "Pont local démarré : saisissez le code d'appairage qu'il affiche.");
      return new Response(null, { status: 204 });
    }
    return new Response(JSON.stringify(current));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderTools() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <LocalTools />
    </QueryClientProvider>,
  );
}

const tool = async (label: string) => within(await screen.findByRole("region", { name: label }));

afterEach(() => vi.unstubAllGlobals());

describe("LocalTools", () => {
  it("explains how to start a bridge that does not answer", async () => {
    const fetchMock = serve(
      state("unreachable", "Pont local non joignable : lancez ./scripts/bridge.ps1 (ou scripts/bridge.sh) sur cet ordinateur."),
    );
    renderTools();

    expect(await screen.findByText("Pont arrêté")).toBeVisible();
    expect(screen.getByText(/scripts\/bridge\.ps1/)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Vérifier à nouveau" }));
    expect(fetchMock.mock.calls.length).toBeGreaterThan(1);
  });

  it("pairs with the code the bridge printed, then lists the tools", async () => {
    const fetchMock = serve(state("unpaired", "Pont local démarré : saisissez le code d'appairage qu'il affiche."));
    renderTools();

    const button = await screen.findByRole("button", { name: "Associer le pont" });
    expect(button).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Code d'appairage"), "abcd-efgh");
    await userEvent.click(button);

    expect(await tool("OpenAI Codex CLI")).toBeTruthy();
    const pairing = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith("/pairing") && init?.method === "POST");
    expect(JSON.parse(String(pairing?.[1]?.body))).toEqual({ code: "abcd-efgh" });
  });

  it("shows each tool with a glyph, a French label and its version", async () => {
    serve(PAIRED);
    renderTools();

    const codex = await tool("OpenAI Codex CLI");
    expect(codex.getByText("Connecté")).toBeVisible();
    expect(codex.getByText("✓")).toBeVisible();
    expect(codex.getByText("0.155.1")).toBeVisible();
    expect(codex.getByText(/compte ChatGPT/)).toBeVisible();
    const gh = await tool("GitHub CLI");
    expect(gh.getByText("Non installé")).toBeVisible();
    expect(gh.getByText("—")).toBeVisible();
  });

  it("gives the official login command when a tool needs one", async () => {
    serve(PAIRED);
    renderTools();

    const claude = await tool("Claude Code");
    expect(claude.getByText("Connexion requise")).toBeVisible();
    expect(claude.getByText("claude auth login")).toBeVisible();
    expect((await tool("OpenAI Codex CLI")).queryByText("codex login")).toBeNull();
  });

  it("says Claude Code is handoff only, and why", async () => {
    serve(PAIRED);
    renderTools();

    const claude = await tool("Claude Code");
    expect(claude.getByText(/Passage de relais disponible/)).toBeVisible();
    expect(claude.getByText(/Pilotage automatique bloqué/)).toBeVisible();
  });

  it("shows a refused code", async () => {
    serve(state("unpaired", "Pont local démarré."), (path, init) =>
      path.endsWith("/pairing") && init?.method === "POST"
        ? new Response(
            JSON.stringify({ error: { code: "pairing_refused", message: "Code d'appairage incorrect.", details: null } }),
            { status: 403 },
          )
        : undefined,
    );
    renderTools();

    await userEvent.type(await screen.findByLabelText("Code d'appairage"), "ZZZZ-ZZZZ");
    await userEvent.click(screen.getByRole("button", { name: "Associer le pont" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Code d'appairage incorrect.");
  });

  it("asks for a new code when the bridge no longer knows NFactory", async () => {
    serve(state("token_rejected", "Le pont ne reconnaît plus NFactory : relancez-le avec -Pair et saisissez le nouveau code."));
    renderTools();

    expect(await screen.findByText("Association perdue")).toBeVisible();
    expect(screen.getByLabelText("Code d'appairage")).toBeVisible();
  });

  it("unpairs on request", async () => {
    const fetchMock = serve(PAIRED);
    renderTools();

    await userEvent.click(await screen.findByRole("button", { name: "Dissocier le pont" }));

    expect(await screen.findByRole("button", { name: "Associer le pont" })).toBeVisible();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(true);
  });
});
