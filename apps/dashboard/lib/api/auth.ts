// Sign-in (ADR-0013): local mode needs none; SSO mode opens a session through Google.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { accessKeys } from "@/lib/api/access";
import { apiGet, apiPost } from "@/lib/api/client";

export type AuthConfig = { mode: "local" | "oidc"; provider: string | null };

export const LOGIN_URL = "/api/v1/auth/login";

export function useAuthConfig() {
  return useQuery({
    queryKey: ["auth", "config"],
    queryFn: () => apiGet<AuthConfig>("/auth/config"),
    staleTime: Infinity,
  });
}

export function useSignOut() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<null>("/auth/logout"),
    onSuccess: () => {
      // Drop every cached answer: they belonged to the session that just ended.
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "auth",
      });
      return client.invalidateQueries({ queryKey: accessKeys.me });
    },
  });
}

const AUTH_ERRORS: Record<string, string> = {
  not_allowed:
    "Ce compte Google n'est pas autorisé dans cet espace. Demandez à un propriétaire de l'ajouter.",
  state: "La connexion a expiré ou a déjà servi. Réessayez.",
  cancelled: "Connexion annulée.",
  provider: "Google n'a pas pu confirmer votre identité. Réessayez.",
};

export function describeAuthError(code: string | null): string | null {
  if (!code) return null;
  return AUTH_ERRORS[code] ?? "La connexion a échoué. Réessayez.";
}
