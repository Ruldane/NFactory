"use client";

import Link from "next/link";

import { ALERT } from "@/components/ui/form-styles";
import { Skeleton } from "@/components/ui/skeleton";
import { useDeleteDocument, useDocuments } from "@/lib/api/knowledge";
import { useProjects } from "@/lib/api/queries";
import { formatDateTime } from "@/lib/format";
import { indexState } from "@/lib/knowledge";

export function DocumentList() {
  const documents = useDocuments(null);
  const projects = useProjects(null);
  const remove = useDeleteDocument();
  const titles = new Map((projects.data?.items ?? []).map((p) => [p.id, p.title]));

  if (documents.error) return <p role="alert" className={ALERT}>{documents.error.message}</p>;
  if (documents.isPending) return <Skeleton className="h-24 bg-navy/8" aria-label="Chargement des documents" />;
  if (documents.data.length === 0) {
    return (
      <p className="border border-dashed border-navy/25 px-5 py-6 text-sm text-navy/70">
        Aucun document pour l&apos;instant. Importez une procédure, un README ou du code : les runs
        s&apos;en serviront et citeront leurs sources.
      </p>
    );
  }
  return (
    <ul className="divide-y divide-navy/10 border-y border-navy/15">
      {documents.data.map((doc) => {
        const state = indexState(doc);
        return (
          <li key={doc.id} className="grid gap-2 py-3 md:grid-cols-[1fr_auto_auto] md:items-center md:gap-6">
            <div className="min-w-0">
              <Link href={`/knowledge/documents/${doc.id}`} className="break-all font-mono text-sm text-navy hover:text-coral-deep hover:underline">
                {doc.path}
              </Link>
              <p className="text-xs text-navy/60">
                {doc.project_id ? (titles.get(doc.project_id) ?? "Projet") : "Tout l'espace"} · révision{" "}
                {doc.revision ?? "—"} · {formatDateTime(doc.created_at)}
              </p>
            </div>
            <p className="text-sm text-navy">
              <span aria-hidden className="mr-1">{state.glyph}</span>
              <span>{state.label}</span>
              <span className="block font-mono text-[11px] text-navy/60">{state.detail}</span>
            </p>
            <button
              type="button"
              onClick={() => remove.mutate(doc.id)}
              disabled={remove.isPending}
              className="justify-self-start font-mono text-[11px] uppercase tracking-wider text-coral-deep hover:underline disabled:opacity-50"
              aria-label={`Retirer ${doc.path}`}
            >
              Retirer
            </button>
          </li>
        );
      })}
    </ul>
  );
}
