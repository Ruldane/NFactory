"use client";

import { type ReactNode, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/lib/api/access";
import {
  describeAuthError,
  LOGIN_URL,
  useAuthConfig,
  useSignOut,
} from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";

// SSO mode (ADR-0013): the app shows only once the API knows who is calling. Local mode
// has a single user and lets everything through, as before.
export function SignInGate({ children }: { children: ReactNode }) {
  const config = useAuthConfig();
  if (config.isPending)
    return <Skeleton className="h-32 bg-navy/8" aria-label="Chargement" />;
  if (config.data?.mode !== "oidc") return children;
  return (
    <SignedIn provider={config.data.provider ?? "SSO"}>{children}</SignedIn>
  );
}

function SignedIn({
  provider,
  children,
}: {
  provider: string;
  children: ReactNode;
}) {
  const me = useMe();
  const signOut = useSignOut();
  if (me.isPending)
    return <Skeleton className="h-32 bg-navy/8" aria-label="Chargement" />;
  if (me.error instanceof ApiError && me.error.status === 401)
    return <SignInScreen provider={provider} />;
  return (
    <>
      <div className="mb-8 flex flex-wrap items-center justify-end gap-3 text-sm text-navy/70">
        <span>
          Connecté :{" "}
          <span className="font-medium text-navy">{me.data?.display_name}</span>
        </span>
        <button
          type="button"
          onClick={() => signOut.mutate()}
          disabled={signOut.isPending}
          className="border border-navy/25 px-3 py-1 text-navy transition-colors hover:border-coral-deep hover:text-coral-deep focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-coral-deep disabled:opacity-45"
        >
          Se déconnecter
        </button>
      </div>
      {children}
    </>
  );
}

function SignInScreen({ provider }: { provider: string }) {
  // Read once from the address the callback sent us back to (`/?auth_error=…`).
  const [error] = useState(() =>
    describeAuthError(
      typeof window === "undefined"
        ? null
        : new URLSearchParams(window.location.search).get("auth_error"),
    ),
  );
  return (
    <section className="mx-auto mt-16 max-w-lg border border-navy/15 bg-cream px-8 py-10">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-coral-deep">
        Connexion
      </p>
      <h1 className="mt-3 font-display text-4xl leading-tight text-navy">
        Entrez dans l&apos;usine
      </h1>
      <p className="mt-4 text-navy/70">
        Cet espace est réservé à son équipe. NFactory reçoit de {provider} votre
        nom et votre adresse e-mail vérifiée, rien d&apos;autre.
      </p>
      {error ? (
        <div
          role="alert"
          className="mt-6 border-l-4 border-coral-deep bg-coral-deep/8 px-5 py-4 text-sm"
        >
          {error}
        </div>
      ) : null}
      <a
        href={LOGIN_URL}
        className="mt-8 inline-block bg-eggplant px-6 py-3 font-medium text-cream transition-colors hover:bg-navy focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-coral-deep"
      >
        Se connecter avec {provider}
      </a>
    </section>
  );
}
