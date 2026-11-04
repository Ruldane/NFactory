import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NewProjectForm } from "@/components/new/new-project-form";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const recipes = {
  items: [
    {
      kind: "excel-automation",
      project_type: "excel",
      label: "Classeur Excel",
      description: "Classeur avec formules",
      deliverable: "non-code",
      outputs: [".xlsx"],
      phase: 1,
      available: true,
    },
  ],
};

type Route = (
  url: string,
  init?: RequestInit,
) => { status: number; body: unknown };

function serve(route: Route) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const { status, body } = route(url, init);
    return new Response(JSON.stringify(body), { status });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderForm() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <NewProjectForm />
    </QueryClientProvider>,
  );
}

async function fillAndSubmit(request: string) {
  await userEvent.click(
    await screen.findByRole("radio", { name: /Classeur Excel/ }),
  );
  await userEvent.type(screen.getByLabelText("Nom du projet"), "Heures");
  await userEvent.type(screen.getByLabelText("Votre besoin"), request);
  await userEvent.click(
    screen.getByRole("button", { name: "Lancer la fabrication" }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  push.mockReset();
});

describe("NewProjectForm", () => {
  it("says the request is handled by AI agents (AI Act, article 50)", async () => {
    serve(() => ({ status: 200, body: recipes }));
    renderForm();

    expect(await screen.findByRole("note")).toHaveTextContent(
      "Votre demande est traitée par des agents d'IA",
    );
  });

  it("creates the project, launches the run and opens its page", async () => {
    const fetchMock = serve((url) => {
      if (url.endsWith("/recipes")) return { status: 200, body: recipes };
      if (url.endsWith("/projects"))
        return { status: 201, body: { id: "proj_1" } };
      return { status: 201, body: { id: "run_1" } };
    });
    renderForm();

    await fillAndSubmit("Un rapport des heures par équipe");

    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/runs/run_1"));
    const runCall = fetchMock.mock.calls.find(([url]) =>
      String(url).endsWith("/runs"),
    );
    expect(runCall?.[0]).toBe("/api/v1/projects/proj_1/runs");
    expect(
      new Headers(runCall?.[1]?.headers).get("Idempotency-Key"),
    ).toBeTruthy();
    expect(JSON.parse(String(runCall?.[1]?.body))).toEqual({
      request: "Un rapport des heures par équipe",
    });
  });

  it("explains why the factory refused the run", async () => {
    serve((url) => {
      if (url.endsWith("/recipes")) return { status: 200, body: recipes };
      if (url.endsWith("/projects"))
        return { status: 201, body: { id: "proj_1" } };
      return {
        status: 409,
        body: {
          error: {
            code: "no_model_configured",
            message: "Aucun moteur IA configuré.",
            details: null,
          },
        },
      };
    });
    renderForm();

    await fillAndSubmit("Un rapport");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Aucun moteur IA configuré.",
    );
    expect(push).not.toHaveBeenCalled();
  });

  it("waits for a need before launching", async () => {
    serve(() => ({ status: 200, body: recipes }));
    renderForm();

    await screen.findByRole("radio", { name: /Classeur Excel/ });
    expect(
      screen.getByRole("button", { name: "Lancer la fabrication" }),
    ).toBeDisabled();
  });
});
