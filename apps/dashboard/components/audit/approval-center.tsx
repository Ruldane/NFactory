"use client";

// The approval center (task 5.4): decisions waiting in the workspace, then the audit
// journal. Buttons appear only when the caller's role allows the action; the API
// enforces the same rule (403 `forbidden`).

import Link from "next/link";

import { DANGER, KICKER, SECONDARY } from "@/components/ui/form-styles";
import { Skeleton } from "@/components/ui/skeleton";
import {
  can,
  useAuditLog,
  useDecide,
  useMe,
  usePendingApprovals,
} from "@/lib/api/access";
import type { ApprovalItem, AuditEntry } from "@/lib/api/types";
import { describeAction, describeDecision } from "@/lib/audit";
import { formatDateTime } from "@/lib/format";

// The API decides only an engine failure from here; other kinds are read on the run.
const DECIDABLE = new Set(["provider_fallback"]);

function Pending({ item, allowed }: { item: ApprovalItem; allowed: boolean }) {
  const decide = useDecide();
  const titleId = `approval-${item.id}`;
  const decidable = DECIDABLE.has(item.action_type);
  return (
    <article
      aria-labelledby={titleId}
      className="space-y-3 border-l-4 border-butter bg-butter/25 px-5 py-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id={titleId} className="font-display text-xl text-navy">
          {item.project_title}
        </h3>
        <span className={KICKER}>{item.action_label}</span>
      </div>
      <p className="text-navy/80">{item.summary}</p>
      <p className="font-mono text-xs text-navy/60">
        Demandé le {formatDateTime(item.created_at)}
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <Link
          href={`/runs/${item.run_id}`}
          className="text-sm text-coral-deep underline underline-offset-4"
        >
          {decidable
            ? "Ouvrir le run pour choisir un autre moteur"
            : "Ouvrir le run"}
        </Link>
        {allowed && decidable ? (
          <>
            <button
              type="button"
              disabled={decide.isPending}
              onClick={() => decide.mutate({ item, approve: true })}
              className={SECONDARY}
            >
              Réessayer le même moteur
            </button>
            <button
              type="button"
              disabled={decide.isPending}
              onClick={() => decide.mutate({ item, approve: false })}
              className={DANGER}
            >
              Arrêter le run
            </button>
          </>
        ) : null}
      </div>
      {decide.isError ? (
        <p role="alert" className="text-sm text-coral-deep">
          {decide.error.message}
        </p>
      ) : null}
    </article>
  );
}

function Journal({ entries }: { entries: AuditEntry[] }) {
  return (
    <table aria-label="Journal d'audit" className="w-full text-left text-sm">
      <thead>
        <tr className={KICKER}>
          <th className="py-2 pr-4 font-normal">Quand</th>
          <th className="py-2 pr-4 font-normal">Qui</th>
          <th className="py-2 pr-4 font-normal">Action</th>
          <th className="py-2 pr-4 font-normal">Cible</th>
          <th className="py-2 font-normal">Décision</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((entry) => (
          <tr key={entry.id} className="border-t border-navy/10 align-top">
            <td className="py-2 pr-4 font-mono text-xs text-navy/70">
              {formatDateTime(entry.timestamp)}
            </td>
            <td className="py-2 pr-4">
              {entry.actor_name ?? entry.actor_id ?? "—"}
            </td>
            <td className="py-2 pr-4 text-navy">
              {describeAction(entry.action)}
            </td>
            <td className="break-all py-2 pr-4 font-mono text-xs">
              {entry.target}
            </td>
            <td className="py-2">{describeDecision(entry.decision)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AuditSection({
  ready,
  allowed,
}: {
  ready: boolean;
  allowed: boolean;
}) {
  const audit = useAuditLog(allowed);
  const entries = audit.data?.pages.flatMap((page) => page.items) ?? [];
  if (!ready) return <Skeleton className="h-28" />;
  if (!allowed) {
    return (
      <p className="text-navy/70">
        Le journal d&apos;audit est réservé aux rôles Relecteur, Administrateur
        et Propriétaire.
      </p>
    );
  }
  if (audit.isPending) return <Skeleton className="h-28" />;
  if (audit.isError) {
    return (
      <p role="alert" className="text-coral-deep">
        {audit.error.message}
      </p>
    );
  }
  if (entries.length === 0) {
    return (
      <p className="text-navy/70">
        Aucune action sensible enregistrée pour l&apos;instant.
      </p>
    );
  }
  return (
    <>
      <Journal entries={entries} />
      {audit.hasNextPage ? (
        <button
          type="button"
          disabled={audit.isFetchingNextPage}
          onClick={() => void audit.fetchNextPage()}
          className={SECONDARY}
        >
          Entrées plus anciennes
        </button>
      ) : null}
    </>
  );
}

function PendingSection({ allowed }: { allowed: boolean }) {
  const pending = usePendingApprovals();
  if (pending.isPending) return <Skeleton className="h-28" />;
  if (pending.isError) {
    return (
      <p role="alert" className="text-coral-deep">
        {pending.error.message}
      </p>
    );
  }
  if (pending.data.items.length === 0) {
    return <p className="text-navy/70">Aucune décision en attente.</p>;
  }
  return (
    <div className="space-y-4">
      {pending.data.items.map((item) => (
        <Pending key={item.id} item={item} allowed={allowed} />
      ))}
    </div>
  );
}

export function ApprovalCenter() {
  const me = useMe();
  const workspace = me.data?.workspaces[0];
  let role = "Chargement de vos droits…";
  if (workspace)
    role = `Votre rôle dans « ${workspace.name} » : ${workspace.role_label}.`;
  else if (!me.isPending)
    role = "Vous n'êtes membre d'aucun espace de travail.";

  return (
    <div className="space-y-12">
      <p className="text-sm text-navy/70">{role}</p>
      <section className="space-y-4">
        <h2 className="font-display text-3xl text-navy">
          En attente de décision
        </h2>
        <PendingSection allowed={can(me.data, "approve")} />
      </section>
      <section className="space-y-4">
        <h2 className="font-display text-3xl text-navy">
          Journal d&apos;audit
        </h2>
        <AuditSection
          ready={me.data !== undefined}
          allowed={can(me.data, "audit")}
        />
      </section>
    </div>
  );
}
