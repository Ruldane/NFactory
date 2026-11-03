import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApprovalCenter } from "@/components/audit/approval-center";
import type { ApprovalItem, AuditPage, Me } from "@/lib/api/types";

const OWNER: Me = {
  user_id: "usr_local",
  display_name: "Moi (local)",
  workspaces: [
    {
      id: "wks_local",
      name: "Local",
      role: "owner",
      role_label: "Propriétaire",
      permissions: ["approve", "audit", "build", "configure", "read"],
    },
  ],
};
const VIEWER: Me = {
  ...OWNER,
  workspaces: [
    {
      ...OWNER.workspaces[0],
      role: "viewer",
      role_label: "Lecteur",
      permissions: ["read"],
    },
  ],
};

const PENDING: ApprovalItem = {
  id: "apr_1",
  status: "pending",
  action_type: "provider_fallback",
  action_label: "Changement de moteur",
  summary: "Le moteur Anthropic a échoué (quota).",
  run_id: "run_1",
  run_state: "APPROVAL_PENDING",
  project_id: "proj_1",
  project_title: "Annuaire",
  created_at: "2026-11-03T09:00:00Z",
  decided_at: null,
};

const AUDIT: AuditPage = {
  items: [
    {
      id: 2,
      timestamp: "2026-11-03T09:05:00Z",
      actor_id: "usr_local",
      actor_name: "Moi (local)",
      action: "run.cancel",
      target: "run_9",
      decision: "applied",
      details: {},
    },
    {
      id: 1,
      timestamp: "2026-11-03T09:00:00Z",
      actor_id: "usr_local",
      actor_name: "Moi (local)",
      action: "settings.run_limits",
      target: "wks_local",
      decision: "applied",
      details: { max_llm_calls: 50 },
    },
  ],
  next_before: null,
};

function serve(me: Me, approvals: ApprovalItem[] = [PENDING]) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST")
      return new Response(JSON.stringify({ id: "run_1" }));
    if (url.startsWith("/api/v1/me")) return new Response(JSON.stringify(me));
    if (url.startsWith("/api/v1/approvals"))
      return new Response(JSON.stringify({ items: approvals }));
    if (url.startsWith("/api/v1/audit")) {
      if (!me.workspaces[0].permissions.includes("audit")) {
        const error = { code: "forbidden", message: "Refusé.", details: null };
        return new Response(JSON.stringify({ error }), { status: 403 });
      }
      return new Response(JSON.stringify(AUDIT));
    }
    return new Response("{}", { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderView() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ApprovalCenter />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("ApprovalCenter", () => {
  it("lists what waits for a decision, with a way to the run", async () => {
    serve(OWNER);
    renderView();

    const item = await screen.findByRole("article", { name: /Annuaire/ });
    expect(within(item).getByText("Changement de moteur")).toBeVisible();
    expect(within(item).getByText(/Anthropic a échoué/)).toBeVisible();
    expect(
      within(item).getByRole("link", { name: /Ouvrir le run/ }),
    ).toHaveAttribute("href", "/runs/run_1");
    expect(screen.getByText(/Propriétaire/)).toBeVisible();
  });

  it("decides from the center", async () => {
    const fetchMock = serve(OWNER);
    renderView();

    const item = await screen.findByRole("article", { name: /Annuaire/ });
    await userEvent.click(
      within(item).getByRole("button", { name: "Arrêter le run" }),
    );

    const post = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "POST",
    );
    expect(post?.[0]).toBe("/api/v1/runs/run_1/approvals/apr_1/reject");
  });

  it("offers buttons only for the decisions the center can take", async () => {
    const plan = {
      ...PENDING,
      id: "apr_plan",
      action_type: "plan",
      action_label: "Validation du plan",
      project_title: "Inventaire",
    };
    serve(OWNER, [plan]);
    renderView();

    const item = await screen.findByRole("article", { name: /Inventaire/ });
    expect(within(item).queryByRole("button")).toBeNull();
    expect(
      within(item).getByRole("link", { name: "Ouvrir le run" }),
    ).toBeVisible();
  });

  it("says when nothing waits", async () => {
    serve(OWNER, []);
    renderView();

    expect(await screen.findByText(/Aucune décision en attente/)).toBeVisible();
  });

  it("shows the audit journal in words", async () => {
    serve(OWNER);
    renderView();

    const journal = await screen.findByRole("table", {
      name: "Journal d'audit",
    });
    expect(within(journal).getByText("Run annulé")).toBeVisible();
    expect(
      within(journal).getByText("Limites des runs modifiées"),
    ).toBeVisible();
    expect(within(journal).getAllByText("Moi (local)")).toHaveLength(2);
  });

  it("gives a viewer no decision buttons and no journal", async () => {
    serve(VIEWER);
    renderView();

    const item = await screen.findByRole("article", { name: /Annuaire/ });
    expect(within(item).queryByRole("button")).toBeNull();
    expect(screen.getAllByText(/Lecteur/).length).toBeGreaterThan(0);
    expect(
      await screen.findByText(/réservé aux rôles Relecteur/),
    ).toBeVisible();
    expect(screen.queryByRole("table")).toBeNull();
  });
});
