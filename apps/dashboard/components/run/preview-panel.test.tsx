import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PreviewPanel, hasPreview } from "@/components/run/preview-panel";
import { completedRun } from "@/components/run/fixtures";
import type { RunDetail } from "@/lib/api/types";

const URL = "http://127.0.0.1:8090/preview/run_1/";

function serve(initial: { running: boolean }, onStart?: () => Response) {
  let running = initial.running;
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
    const method = init?.method ?? "GET";
    if (method === "POST") {
      if (onStart) return onStart();
      running = true;
      return reply({ running: true, url: URL, expires_in_s: 900 });
    }
    if (method === "DELETE") {
      running = false;
      return new Response(null, { status: 204 });
    }
    return reply(running ? { running: true, url: URL, expires_in_s: 600 } : { running: false, url: null, expires_in_s: null });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PreviewPanel runId="run_1" />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("PreviewPanel", () => {
  it("starts the app in the sandbox and frames it", async () => {
    const fetchMock = serve({ running: false });
    renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "Lancer l'aperçu" }));

    const frame = await screen.findByTitle("Aperçu de l'application générée");
    expect(frame).toHaveAttribute("src", URL);
    expect(frame.getAttribute("sandbox")).toContain("allow-scripts");
    expect(screen.getByRole("link", { name: /Ouvrir dans un onglet/ })).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText(/s'arrête dans 15 min/)).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/runs/run_1/preview", expect.objectContaining({ method: "POST" }));
  });

  it("stops a running preview", async () => {
    const fetchMock = serve({ running: true });
    renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "Arrêter l'aperçu" }));

    expect(await screen.findByRole("button", { name: "Lancer l'aperçu" })).toBeVisible();
    expect(screen.queryByTitle("Aperçu de l'application générée")).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/runs/run_1/preview", expect.objectContaining({ method: "DELETE" }));
  });

  it("says why a preview could not start", async () => {
    const busy = { error: { code: "preview_busy", message: "Trop d'aperçus ouverts : fermez-en un puis réessayez.", details: null } };
    serve({ running: false }, () => new Response(JSON.stringify(busy), { status: 503 }));
    renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "Lancer l'aperçu" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Trop d'aperçus ouverts");
  });
});

describe("hasPreview", () => {
  const withPreview = (output: Record<string, unknown>, state = "COMPLETED"): RunDetail => ({
    ...completedRun,
    state: state as RunDetail["state"],
    steps: completedRun.steps.map((s) => (s.name === "package" ? { ...s, output } : s)),
  });

  it("is true only for a completed run whose recipe declared a preview", () => {
    const preview = { preview: { argv: ["python", "tools/preview.py"], port: 8000 } };
    expect(hasPreview(withPreview(preview))).toBe(true);
    expect(hasPreview(withPreview({}))).toBe(false);
    expect(hasPreview(withPreview(preview, "FAILED"))).toBe(false);
  });
});
