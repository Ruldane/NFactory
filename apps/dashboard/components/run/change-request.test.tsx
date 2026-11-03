import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChangeRequest } from "@/components/run/change-request";
import { completedRun } from "@/components/run/fixtures";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

function renderForm() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ChangeRequest run={completedRun} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  push.mockReset();
});

describe("ChangeRequest", () => {
  it("launches a child run of the delivered run and opens it", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ...completedRun, id: "run_child" }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    renderForm();

    await userEvent.type(screen.getByLabelText("Évolution demandée"), "Ajoute un filtre par département");
    await userEvent.click(screen.getByRole("button", { name: "Lancer l'évolution" }));

    expect(push).toHaveBeenCalledWith("/runs/run_child");
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`/api/v1/projects/${completedRun.project.id}/runs`);
    expect(JSON.parse(String(init.body))).toEqual({
      request: "Ajoute un filtre par département",
      parent_run_id: completedRun.id,
    });
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("waits for a request before launching", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderForm();

    expect(screen.getByRole("button", { name: "Lancer l'évolution" })).toBeDisabled();
  });

  it("shows why the change could not start", async () => {
    const refused = { error: { code: "parent_not_completed", message: "Seul un run livré peut recevoir une évolution.", details: null } };
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(refused), { status: 409 })));
    renderForm();

    await userEvent.type(screen.getByLabelText("Évolution demandée"), "Ajoute un champ");
    await userEvent.click(screen.getByRole("button", { name: "Lancer l'évolution" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Seul un run livré");
    expect(push).not.toHaveBeenCalled();
  });
});
