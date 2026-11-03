import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RecipesView } from "@/components/recipes/recipes-view";
import { SaveRecipe } from "@/components/recipes/save-recipe";
import { completedRun } from "@/components/run/fixtures";
import type { SavedRecipe } from "@/lib/api/types";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const RECIPE: SavedRecipe = {
  id: "rcp_1",
  name: "Suivi des dépenses",
  description: "Classeur du service",
  project_type: "excel",
  template_id: null,
  request: "Un classeur Excel de suivi des dépenses.",
  source_run_id: "run_ok",
  created_by: "usr_local",
  created_at: "2026-11-03T09:00:00Z",
  uses: 2,
  last_used_at: "2026-11-03T10:00:00Z",
};

function serve(recipes: SavedRecipe[]) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST" && url.endsWith("/launch")) {
      return new Response(JSON.stringify({ ...completedRun, id: "run_new" }), {
        status: 201,
      });
    }
    if (init?.method === "POST")
      return new Response(JSON.stringify(RECIPE), { status: 201 });
    if (init?.method === "DELETE") return new Response(null, { status: 204 });
    return new Response(JSON.stringify({ items: recipes }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function wrap(node: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{node}</QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  push.mockReset();
});

describe("RecipesView", () => {
  it("lists the workspace's recipes with their request and use count", async () => {
    serve([RECIPE]);
    wrap(<RecipesView />);

    const card = await screen.findByRole("article", {
      name: "Suivi des dépenses",
    });
    expect(within(card).getByText(/suivi des dépenses\./)).toBeVisible();
    expect(within(card).getByText("Excel")).toBeVisible();
    expect(within(card).getByText(/Relancée 2 fois/)).toBeVisible();
    expect(
      within(card).getByRole("link", { name: /run d'origine/ }),
    ).toHaveAttribute("href", "/runs/run_ok");
  });

  it("replays a recipe once and opens the new run", async () => {
    const fetchMock = serve([RECIPE]);
    wrap(<RecipesView />);

    const card = await screen.findByRole("article", {
      name: "Suivi des dépenses",
    });
    await userEvent.click(
      within(card).getByRole("button", { name: "Relancer" }),
    );

    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/runs/run_new"));
    const launch = fetchMock.mock.calls.find(([url]) =>
      String(url).endsWith("/launch"),
    );
    expect(launch?.[0]).toBe("/api/v1/saved-recipes/rcp_1/launch");
    const headers = launch?.[1]?.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBeTruthy();
  });

  it("says how to make a first recipe", async () => {
    serve([]);
    wrap(<RecipesView />);

    expect(
      await screen.findByText(/Aucune recette pour l'instant/),
    ).toBeVisible();
  });
});

describe("SaveRecipe", () => {
  it("saves a delivered run under a name", async () => {
    const fetchMock = serve([]);
    wrap(<SaveRecipe run={completedRun} />);

    const name = screen.getByLabelText("Nom de la recette");
    expect(name).toHaveValue(completedRun.project.title);
    await userEvent.clear(name);
    await userEvent.type(name, "Annuaire réutilisable");
    await userEvent.click(
      screen.getByRole("button", { name: "Enregistrer comme recette" }),
    );

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Recette enregistrée",
    );
    const post = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "POST",
    );
    expect(post?.[0]).toBe("/api/v1/saved-recipes");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      run_id: completedRun.id,
      name: "Annuaire réutilisable",
    });
  });
});
