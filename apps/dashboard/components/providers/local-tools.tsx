"use client";

// Local coding tools (codex, claude, gh) seen through the bridge on this computer
// (tasks 4.1, 4.2). The bridge runs outside Docker; NFactory pairs with it once, with the
// code it prints. No login happens here: each tool keeps its own official login flow.

import { cn } from "cn";
import { useState, type FormEvent } from "react";

import { TONE_CLASSES } from "@/components/runs/tone";
import { ALERT, FIELD, KICKER, PRIMARY, SECONDARY } from "@/components/ui/form-styles";
import { Skeleton } from "@/components/ui/skeleton";
import { useLocalRuntimes, usePairBridge, useUnpairBridge } from "@/lib/api/local-runtimes";
import type { LocalRuntime } from "@/lib/api/types";
import { describeBridgeStatus, describeRuntimeStatus } from "@/lib/local-runtime-status";
import type { StateDescription } from "@/lib/run-state";

const LOGINS: Record<string, string> = {
  chatgpt: "compte ChatGPT",
  api_key: "clé API",
};

const MODES: Record<string, Record<string, string>> = {
  runtime: {
    available: "Pilotable par NFactory avec votre accord à chaque tâche (tâche 4.3, à venir)",
    blocked_by_policy: "Pilotage automatique bloqué : conformité de l'abonnement à vérifier",
  },
  handoff: {
    available: "Passage de relais disponible : vous lancez l'outil, NFactory importe le résultat",
    blocked_by_policy: "Passage de relais indisponible",
  },
};

function StatusTag({ state }: { state: StateDescription }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 font-mono text-[11px] font-medium uppercase tracking-wider",
        TONE_CLASSES[state.tone],
      )}
    >
      <span aria-hidden>{state.glyph}</span>
      {state.label}
    </span>
  );
}

function PairingForm() {
  const [code, setCode] = useState("");
  const pair = usePairBridge();

  function submit(event: FormEvent) {
    event.preventDefault();
    pair.mutate(code.trim());
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
      <label className="space-y-1">
        <span className={KICKER}>Code d&apos;appairage</span>
        <input
          className={cn(FIELD, "w-40 uppercase tracking-[0.2em]")}
          value={code}
          onChange={(event) => setCode(event.target.value)}
          placeholder="ABCD-EFGH"
          autoComplete="off"
          spellCheck={false}
          maxLength={9}
        />
      </label>
      <button type="submit" className={PRIMARY} disabled={code.trim().length < 8 || pair.isPending}>
        Associer le pont
      </button>
      {pair.error ? (
        <div role="alert" className={cn(ALERT, "basis-full")}>
          {pair.error.message}
        </div>
      ) : null}
    </form>
  );
}

function ToolCard({ tool }: { tool: LocalRuntime }) {
  const titleId = `local-tool-${tool.kind}`;
  const modes = Object.entries(tool.modes)
    .map(([mode, value]) => MODES[mode]?.[value])
    .filter((text): text is string => Boolean(text));
  return (
    <section aria-labelledby={titleId} className="space-y-3 border border-navy/15 bg-cream/60 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={titleId} className="font-display text-lg text-navy">
          {tool.label}
        </h3>
        <StatusTag state={describeRuntimeStatus(tool.status)} />
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-navy/60">Version</dt>
        <dd className="font-mono text-navy">{tool.version ?? "—"}</dd>
        {tool.login ? (
          <>
            <dt className="text-navy/60">Connexion</dt>
            <dd className="text-navy">{LOGINS[tool.login] ?? tool.login}</dd>
          </>
        ) : null}
      </dl>
      {tool.status === "needs_login" && tool.login_command ? (
        <p className="text-sm text-navy/80">
          Connectez-vous dans votre terminal, avec la commande officielle :{" "}
          <code className="bg-navy/6 px-1.5 py-0.5 font-mono text-[13px]">{tool.login_command}</code>
        </p>
      ) : null}
      {modes.length ? (
        <ul className="space-y-1 text-sm text-navy/75">
          {modes.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      ) : null}
      {tool.detail ? <p className="text-sm text-navy/60">{tool.detail}</p> : null}
    </section>
  );
}

export function LocalTools() {
  const view = useLocalRuntimes();
  const unpair = useUnpairBridge();

  if (view.error) return <div role="alert" className={ALERT}>{view.error.message}</div>;
  if (!view.data) {
    return <Skeleton className="h-40 bg-navy/8" aria-label="Recherche du pont local" />;
  }

  const { bridge, runtimes } = view.data;
  const needsCode = bridge.status === "unpaired" || bridge.status === "token_rejected";
  return (
    <div className="space-y-5">
      <div className="space-y-3 border-l-4 border-eggplant/40 pl-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium text-navy">Pont local</span>
          <StatusTag state={describeBridgeStatus(bridge.status)} />
          {bridge.version ? <span className="font-mono text-xs text-navy/60">v{bridge.version}</span> : null}
        </div>
        <p className="max-w-3xl text-sm text-navy/75">{bridge.message}</p>
        {bridge.status === "unreachable" ? (
          <button type="button" className={SECONDARY} onClick={() => view.refetch()} disabled={view.isFetching}>
            Vérifier à nouveau
          </button>
        ) : null}
        {needsCode ? <PairingForm /> : null}
        {bridge.status === "paired" ? (
          <div className="flex flex-wrap gap-3">
            <button type="button" className={SECONDARY} onClick={() => view.refetch()} disabled={view.isFetching}>
              Actualiser
            </button>
            <button type="button" className={SECONDARY} onClick={() => unpair.mutate()} disabled={unpair.isPending}>
              Dissocier le pont
            </button>
          </div>
        ) : null}
      </div>
      {runtimes.length ? (
        <div className="grid gap-4 md:grid-cols-3">
          {runtimes.map((tool) => (
            <ToolCard key={tool.kind} tool={tool} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
