import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectList } from "@/components/projects/project-list";
import type { Page, Project } from "@/lib/api/types";

const project = (over: Partial<Project>): Project => ({
  id: "proj_x",
  title: "Projet",
  description: "",
  type: "api",
  template_id: null,
  status: "active",
  is_demo: false,
  created_at: "2026-10-28T09:00:00Z",
  updated_at: "2026-10-28T09:00:00Z",
  ...over,
});

const page: Page<Project> = {
  items: [
    project({ id: "proj_a", title: "API d'inventaire", type: "api", is_demo: true }),
    project({ id: "proj_b", title: "Rapport KPI", type: "excel" }),
  ],
  total: 2,
  limit: 100,
  offset: 0,
};

function renderList() {
  const fetchMock = vi.fn(async (_input: RequestInfo | URL) => new Response(JSON.stringify(page), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ProjectList />
    </QueryClientProvider>,
  );
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("ProjectList", () => {
  it("lists projects and marks demo ones", async () => {
    renderList();

    expect(await screen.findByText("API d'inventaire")).toBeVisible();
    expect(screen.getByText("Rapport KPI")).toBeVisible();
    expect(screen.getAllByText("Démo")).toHaveLength(1);
  });

  it("filters by type through the API", async () => {
    const fetchMock = renderList();
    await screen.findByText("Rapport KPI");

    await userEvent.click(screen.getByRole("radio", { name: "Excel" }));

    const lastUrl = String(fetchMock.mock.calls.at(-1)?.[0]);
    expect(lastUrl).toContain("type=excel");
    expect(screen.getByRole("radio", { name: "Excel" })).toBeChecked();
  });
});
