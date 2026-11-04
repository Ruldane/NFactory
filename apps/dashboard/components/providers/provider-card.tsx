"use client";

// One provider: honest status, configuration form, consented connection test, catalog.
// The key field is write-only: it is cleared once saved and never filled from the API.

import { type FormEvent, useId, useState } from "react";

import { ModelCatalog } from "@/components/providers/model-catalog";
import { regionOption, ResidencyNote } from "@/components/providers/residency-note";
import { ProviderStatusBadge } from "@/components/providers/status-badge";
import { ALERT, DANGER, FIELD, KICKER, PRIMARY, SECONDARY } from "@/components/ui/form-styles";
import { useConfigureProvider, useRemoveProvider, useValidateProvider } from "@/lib/api/providers";
import type { ProviderConfigInput, ProviderView } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";

type Notice = { ok: boolean; text: string } | null;

export function ProviderCard({ provider }: { provider: ProviderView }) {
  const headingId = useId();
  return (
    <section
      aria-labelledby={headingId}
      className={
        provider.available
          ? "space-y-5 border border-navy/15 bg-cream px-5 py-5"
          : "space-y-2 border border-dashed border-navy/25 px-5 py-4 text-navy/55"
      }
    >
      <header className="flex flex-wrap items-center gap-3">
        <h3 id={headingId} className="font-display text-xl text-navy">
          {provider.label}
        </h3>
        {provider.available ? (
          <ProviderStatusBadge status={provider.status} />
        ) : (
          <span className="font-mono text-[11px] uppercase tracking-[0.2em]">
            Phase {provider.phase}
          </span>
        )}
        {provider.docs_url ? (
          <a
            href={provider.docs_url}
            target="_blank"
            rel="noreferrer"
            className="ml-auto text-xs text-navy/60 underline-offset-2 hover:underline"
          >
            Documentation officielle
          </a>
        ) : null}
      </header>
      <ResidencyNote residency={provider.residency} />
      {provider.available ? (
        <ProviderBody provider={provider} />
      ) : (
        <p className="text-sm">Agent de code local : piloté par NFactory à partir de la phase 4.</p>
      )}
    </section>
  );
}

function ProviderBody({ provider }: { provider: ProviderView }) {
  const id = useId();
  const configure = useConfigureProvider(provider.kind);
  const validate = useValidateProvider(provider.kind);
  const remove = useRemoveProvider(provider.kind);
  const [apiKey, setApiKey] = useState("");
  const [useEnv, setUseEnv] = useState(false);
  const [region, setRegion] = useState(provider.region ?? provider.regions[0]?.id ?? null);
  const [workspaceId, setWorkspaceId] = useState(provider.workspace_id ?? "");
  const [baseUrl, setBaseUrl] = useState(provider.base_url ?? "");
  const [notice, setNotice] = useState<Notice>(null);
  const configured = provider.status !== "not_configured";
  const needsWorkspace = provider.regions.find((r) => r.id === region)?.needs_workspace ?? false;

  function submit(event: FormEvent) {
    event.preventDefault();
    const input: ProviderConfigInput = { region };
    if (apiKey) input.api_key = apiKey;
    if (useEnv) input.use_env_key = true;
    if (needsWorkspace) input.workspace_id = workspaceId.trim();
    if (provider.custom_url) input.base_url = baseUrl.trim();
    setNotice(null);
    configure.mutate(input, {
      onSuccess: () => {
        setApiKey("");
        setNotice({ ok: true, text: "Configuration enregistrée. Testez la connexion pour l'activer." });
      },
      onError: (error) => setNotice({ ok: false, text: error.message }),
    });
  }

  function test() {
    setNotice(null);
    validate.mutate(undefined, {
      onSuccess: (result) => setNotice({ ok: result.ok, text: result.message }),
      onError: (error) => setNotice({ ok: false, text: error.message }),
    });
  }

  return (
    <div className="space-y-5">
      <p className="text-sm text-navy/70">
        {provider.key_source === "stored" ? "Clé enregistrée, chiffrée sur ce poste. " : null}
        {provider.key_source === "env" ? `Clé lue depuis ${provider.env_key}. ` : null}
        {provider.last_checked_at ? `Dernier test le ${formatDateTime(provider.last_checked_at)}.` : null}
      </p>
      {provider.last_error && !notice ? (
        <div className={ALERT}>{provider.last_error.message}</div>
      ) : null}
      {provider.discovery ? null : (
        <p className="text-sm text-navy/70">
          Ce fournisseur ne publie pas sa liste de modèles : ajoutez un modèle au catalogue avant
          de tester la connexion.
        </p>
      )}
      <form onSubmit={submit} className="grid gap-4 md:grid-cols-2">
        {provider.needs_key || provider.kind === "custom_openai_compatible" ? (
          <div className="space-y-1">
            <label htmlFor={`${id}-key`} className={`block ${KICKER}`}>
              Clé API
            </label>
            <input
              id={`${id}-key`}
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={provider.key_source ? "Laisser vide pour garder la clé actuelle" : ""}
              className={FIELD}
            />
            {provider.env_key_available ? (
              <label className="flex items-center gap-2 pt-1 text-sm text-navy/75">
                <input type="checkbox" checked={useEnv} onChange={(e) => setUseEnv(e.target.checked)} />
                Utiliser {provider.env_key} défini sur le serveur
              </label>
            ) : null}
          </div>
        ) : null}
        {provider.regions.length > 1 ? (
          <div className="space-y-1">
            <label htmlFor={`${id}-region`} className={`block ${KICKER}`}>
              Région
            </label>
            <select
              id={`${id}-region`}
              value={region ?? ""}
              onChange={(e) => setRegion(e.target.value)}
              className={FIELD}
            >
              {provider.regions.map((r) => (
                <option key={r.id} value={r.id}>
                  {regionOption(r)}
                </option>
              ))}
            </select>
          </div>
        ) : null}
        {needsWorkspace ? (
          <div className="space-y-1">
            <label htmlFor={`${id}-ws`} className={`block ${KICKER}`}>
              Identifiant d&apos;espace de travail
            </label>
            <input
              id={`${id}-ws`}
              required
              value={workspaceId}
              onChange={(e) => setWorkspaceId(e.target.value)}
              className={FIELD}
            />
          </div>
        ) : null}
        {provider.custom_url ? (
          <div className="space-y-1 md:col-span-2">
            <label htmlFor={`${id}-url`} className={`block ${KICKER}`}>
              URL de base
            </label>
            <input
              id={`${id}-url`}
              type="url"
              required
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              className={FIELD}
            />
          </div>
        ) : null}
        <div className="flex flex-wrap items-center gap-3 md:col-span-2">
          <button type="submit" disabled={configure.isPending} className={PRIMARY}>
            Enregistrer
          </button>
          {configured ? (
            <>
              <button type="button" onClick={test} disabled={validate.isPending} className={SECONDARY}>
                {validate.isPending ? "Test en cours…" : "Tester la connexion"}
              </button>
              <button
                type="button"
                onClick={() => remove.mutate(undefined, { onSuccess: () => setNotice(null) })}
                disabled={remove.isPending}
                className={DANGER}
              >
                Retirer
              </button>
            </>
          ) : null}
        </div>
      </form>
      {notice ? (
        notice.ok ? (
          <p role="status" className="text-sm text-forest">
            ✓ {notice.text}
          </p>
        ) : (
          <div role="alert" className={ALERT}>
            {notice.text}
          </div>
        )
      ) : null}
      {configured ? <ModelCatalog kind={provider.kind} /> : null}
    </div>
  );
}
