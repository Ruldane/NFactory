import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MembersSection } from "@/components/settings/members-section";
import type { Items, Me, Member, Permission } from "@/lib/api/types";

const me = (permissions: Permission[]): Me => ({
  user_id: "usr_local",
  display_name: "Moi (local)",
  workspaces: [{ id: "wks_local", name: "Mon espace", role: "owner", role_label: "Propriétaire", permissions }],
});

const MEMBERS: Items<Member> = {
  items: [
    {
      user_id: "usr_ada",
      display_name: "Ada L.",
      email: "ada@example.fr",
      role: "developer",
      role_label: "Développeur",
      is_owner: false,
      created_at: "2026-11-01T09:00:00Z",
    },
    {
      user_id: "usr_local",
      display_name: "Moi (local)",
      email: null,
      role: "owner",
      role_label: "Propriétaire",
      is_owner: true,
      created_at: "2026-11-01T09:00:00Z",
    },
  ],
};

function serve(permissions: Permission[]) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "DELETE") {
      return new Response(JSON.stringify({ user_id: "usr_ada", anonymised: true }));
    }
    if (url === "/api/v1/me") return new Response(JSON.stringify(me(permissions)));
    return new Response(JSON.stringify(MEMBERS));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderSection() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MembersSection />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("MembersSection", () => {
  it("lists the members with their role, and never offers to erase an owner", async () => {
    serve(["read", "configure"]);
    renderSection();

    expect(await screen.findByText("Ada L.")).toBeVisible();
    expect(screen.getByText("ada@example.fr")).toBeVisible();
    expect(screen.getByText("Développeur")).toBeVisible();
    expect(screen.getAllByRole("button", { name: "Effacer" })).toHaveLength(1);
    expect(screen.getByText(/Propriétaire de l'espace/)).toBeVisible();
  });

  it("erases a member after a confirmation", async () => {
    const fetchMock = serve(["read", "configure"]);
    renderSection();

    await userEvent.click(await screen.findByRole("button", { name: "Effacer" }));
    await userEvent.click(screen.getByRole("button", { name: "Oui, effacer Ada L." }));

    expect(await screen.findByRole("status")).toHaveTextContent("Ada L. a été effacé");
    const erase = fetchMock.mock.calls.find(([, init]) => init?.method === "DELETE");
    expect(erase?.[0]).toBe("/api/v1/members/usr_ada");
  });

  it("is hidden from a member who may not configure", async () => {
    const fetchMock = serve(["read", "build"]);
    renderSection();

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByRole("heading", { name: "Membres" })).toBeNull();
    expect(fetchMock.mock.calls.every(([url]) => !String(url).includes("/members"))).toBe(true);
  });
});
