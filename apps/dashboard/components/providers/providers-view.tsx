"use client";

import { LocalTools } from "@/components/providers/local-tools";
import { ProviderCard } from "@/components/providers/provider-card";
import { RoutingEditor } from "@/components/providers/routing-editor";
import { ALERT } from "@/components/ui/form-styles";
import { Skeleton } from "@/components/ui/skeleton";
import { useProviders } from "@/lib/api/providers";

export function ProvidersView() {
  const providers = useProviders();

  if (providers.error) return <div role="alert" className={ALERT}>{providers.error.message}</div>;
  if (!providers.data) {
    return <Skeleton className="h-96 bg-navy/8" aria-label="Chargement des moteurs IA" />;
  }

  const chat = providers.data.filter((p) => p.family !== "coding_agent");
  return (
    <div className="space-y-12">
      <section className="space-y-4">
        <h2 className="font-display text-2xl text-navy">Routage des rôles</h2>
        <RoutingEditor providers={providers.data} />
      </section>
      <section className="space-y-4">
        <h2 className="font-display text-2xl text-navy">Fournisseurs</h2>
        <p className="max-w-3xl text-sm text-navy/70">
          Une clé est chiffrée sur ce poste et n&apos;est jamais réaffichée. Un fournisseur devient
          « Connecté » seulement après un test réussi que vous lancez.
        </p>
        <div className="grid gap-5 xl:grid-cols-2">
          {chat.map((provider) => (
            <ProviderCard key={provider.kind} provider={provider} />
          ))}
        </div>
      </section>
      <section className="space-y-4">
        <h2 className="font-display text-2xl text-navy">Outils locaux</h2>
        <p className="max-w-3xl text-sm text-navy/70">
          Codex, Claude Code et GitHub CLI restent sur cet ordinateur, avec leur propre connexion :
          NFactory ne lit ni ne demande aucun jeton. Le pont local les détecte et vous les présente.
        </p>
        <LocalTools />
      </section>
    </div>
  );
}
