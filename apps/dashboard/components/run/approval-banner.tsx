"use client";

// A run paused because its engine failed (routing fallback "ask_user"). The user retries
// the same engine, picks a replacement, or stops the run. Nothing is switched alone.

import { type FormEvent, useState } from "react";

import { ALERT, DANGER, FIELD, KICKER, PRIMARY, SECONDARY } from "@/components/ui/form-styles";
import { useCatalog, useProviders } from "@/lib/api/providers";
import { useApproveRun, useRejectRun } from "@/lib/api/queries";
import type { Approval, RunDetail } from "@/lib/api/types";
import { ROLE_LABELS } from "@/lib/provider-status";

export function ApprovalBanner({ run, approval }: { run: RunDetail; approval: Approval }) {
  const approve = useApproveRun(run.id);
  const reject = useRejectRun(run.id);
  const providers = useProviders();
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const catalog = useCatalog(provider, provider !== "");
  const busy = approve.isPending || reject.isPending;
  const { role = "", provider: failed = "", model: failedModel = "" } = approval.details;
  const failedLabel = providers.data?.find((p) => p.kind === failed)?.label ?? failed;
  const connected = (providers.data ?? []).filter((p) => p.available && p.status === "connected");

  function replace(event: FormEvent) {
    event.preventDefault();
    approve.mutate({ approvalId: approval.id, replacement: { provider, model: model.trim() } });
  }

  return (
    <div role="alert" className="space-y-4 border-l-4 border-butter bg-butter/30 px-5 py-4">
      <p className="font-medium text-eggplant">{approval.summary}</p>
      <p className="text-sm text-navy/80">
        Le moteur {failedLabel} ({failedModel}) du rôle « {ROLE_LABELS[role] ?? role} » a échoué.
        Le run est en pause : aucun autre moteur n&apos;a été utilisé. Les étapes déjà terminées
        seront conservées.
      </p>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          disabled={busy}
          onClick={() => approve.mutate({ approvalId: approval.id, replacement: null })}
          className={SECONDARY}
        >
          Réessayer le même moteur
        </button>
        <button type="button" disabled={busy} onClick={() => reject.mutate(approval.id)} className={DANGER}>
          Arrêter le run
        </button>
      </div>
      <form onSubmit={replace} className="grid gap-2 md:grid-cols-[1fr_1fr_auto] md:items-end">
        <label className="space-y-1">
          <span className={`block ${KICKER}`}>Moteur de remplacement</span>
          <select
            value={provider}
            onChange={(e) => {
              setProvider(e.target.value);
              setModel("");
            }}
            className={FIELD}
          >
            <option value="">Choisir…</option>
            {connected.map((p) => (
              <option key={p.kind} value={p.kind}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className={`block ${KICKER}`}>Modèle de remplacement</span>
          <input
            list="replacement-models"
            value={model}
            disabled={provider === ""}
            onChange={(e) => setModel(e.target.value)}
            className={FIELD}
          />
          <datalist id="replacement-models">
            {(catalog.data ?? []).map((m) => (
              <option key={m.model_id} value={m.model_id} />
            ))}
          </datalist>
        </label>
        <button type="submit" disabled={busy || !provider || !model.trim()} className={PRIMARY}>
          Reprendre avec ce moteur
        </button>
      </form>
      {approve.error || reject.error ? (
        <p className={ALERT}>{(approve.error ?? reject.error)?.message}</p>
      ) : null}
    </div>
  );
}
