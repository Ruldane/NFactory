import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SignInGate } from "@/components/auth/sign-in-gate";
import type { Me } from "@/lib/api/types";

const ADA: Me = {
  user_id: "usr_ada",
  display_name: "Ada Lovelace",
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

const UNAUTHENTICATED = JSON.stringify({
  error: {
    code: "not_authenticated",
    message: "Connectez-vous pour continuer.",
    details: null,
  },
});

function serve(mode: "local" | "oidc", me: Me | null, contact: string | null = null) {
  let signedIn = me;
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.startsWith("/api/v1/auth/config"))
      return new Response(
        JSON.stringify(
          mode === "oidc"
            ? { mode, provider: "Google", session_hours: 12, privacy_contact: contact }
            : { mode, provider: null },
        ),
      );
    if (url.startsWith("/api/v1/auth/logout") && init?.method === "POST") {
      signedIn = null;
      return new Response(null, { status: 204 });
    }
    if (url.startsWith("/api/v1/me"))
      return signedIn
        ? new Response(JSON.stringify(signedIn))
        : new Response(UNAUTHENTICATED, { status: 401 });
    return new Response("{}", { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderGate() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <SignInGate>
        <p>Contenu protégé</p>
      </SignInGate>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("SignInGate", () => {
  it("lets everything through in local mode", async () => {
    serve("local", null);
    renderGate();

    expect(await screen.findByText("Contenu protégé")).toBeVisible();
    expect(screen.queryByText(/Se connecter/)).not.toBeInTheDocument();
  });

  it("asks a signed-out visitor to sign in with Google and hides the app", async () => {
    serve("oidc", null);
    renderGate();

    const link = await screen.findByRole("link", {
      name: "Se connecter avec Google",
    });
    expect(link).toHaveAttribute("href", "/api/v1/auth/login");
    expect(screen.queryByText("Contenu protégé")).not.toBeInTheDocument();
  });

  it("tells a visitor what happens to their data before they sign in", async () => {
    serve("oidc", null, "dpo@example.fr");
    renderGate();

    const notice = await screen.findByRole("region", { name: "Vos données" });
    expect(notice).toHaveTextContent(/nom, votre adresse e-mail vérifiée et votre identifiant Google/);
    expect(notice).toHaveTextContent(/12 h/);
    expect(notice).toHaveTextContent(/strictement nécessaire/);
    expect(notice).toHaveTextContent(/dpo@example.fr/);
    expect(screen.getByRole("link", { name: "CNIL" })).toHaveAttribute(
      "href",
      "https://www.cnil.fr/fr/adresser-une-plainte",
    );
  });

  it("points to the space's administrator when no privacy contact is set", async () => {
    serve("oidc", null);
    renderGate();

    expect(await screen.findByRole("region", { name: "Vos données" })).toHaveTextContent(
      /administrateur de cet espace/,
    );
  });

  it("says why a sign-in was refused", async () => {
    window.history.replaceState(null, "", "/?auth_error=not_allowed");
    serve("oidc", null);
    renderGate();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ce compte Google n'est pas autorisé",
    );
  });

  it("shows who is signed in and signs out", async () => {
    const fetchMock = serve("oidc", ADA);
    renderGate();

    expect(await screen.findByText("Contenu protégé")).toBeVisible();
    expect(screen.getByText("Ada Lovelace")).toBeVisible();

    await userEvent.click(
      screen.getByRole("button", { name: "Se déconnecter" }),
    );

    expect(
      await screen.findByRole("link", { name: "Se connecter avec Google" }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/logout",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
