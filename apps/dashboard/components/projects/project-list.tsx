"use client";

import { useState } from "react";

import { projectTypeLabel } from "@/components/projects/project-types";
import { TypeFilter } from "@/components/projects/type-filter";
import { ConfirmButton } from "@/components/ui/confirm-button";
import { Skeleton } from "@/components/ui/skeleton";
import { can, useMe } from "@/lib/api/access";
import { useDeleteProject, useProjects } from "@/lib/api/queries";
import type { ProjectType } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";

export function ProjectList() {
  const [type, setType] = useState<ProjectType | null>(null);
  const { data, error, isPending } = useProjects(type);
  const me = useMe();
  const canDelete = can(me.data, "configure");
  const deletion = useDeleteProject();

  return (
    <div className="space-y-6">
      <TypeFilter value={type} onChange={setType} />
      {deletion.error ? (
        <div role="alert" className="border-l-4 border-coral-deep bg-coral-deep/8 px-5 py-4 text-sm">
          {deletion.error.message}
        </div>
      ) : null}
      {error ? (
        <div role="alert" className="border-l-4 border-coral-deep bg-coral-deep/8 px-5 py-4 text-sm">
          {error.message}
        </div>
      ) : isPending ? (
        <Skeleton className="h-64 bg-navy/8" aria-label="Chargement des projets" />
      ) : data.items.length === 0 ? (
        <p className="border border-dashed border-navy/25 px-6 py-10 text-center text-sm text-navy/70">
          Aucun projet de ce type.
        </p>
      ) : (
        <ul className="grid gap-px overflow-hidden border border-navy/10 bg-navy/10 md:grid-cols-2">
          {data.items.map((project) => (
            <li key={project.id} className="flex flex-col gap-3 bg-cream p-5">
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-[11px] uppercase tracking-wider text-coral-deep">
                  {projectTypeLabel(project.type)}
                </span>
                {project.is_demo ? (
                  <span className="rounded-sm bg-butter px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase text-eggplant">
                    Démo
                  </span>
                ) : null}
              </div>
              <h2 className="font-display text-xl text-navy">{project.title}</h2>
              <p className="text-sm text-navy/70">{project.description}</p>
              <p className="mt-auto font-mono text-[11px] text-navy/50">
                {project.id} · {formatDateTime(project.created_at)}
              </p>
              {canDelete ? (
                <ConfirmButton
                  label="Supprimer"
                  ariaLabel="Supprimer le projet"
                  confirmLabel={`Oui, supprimer « ${project.title} »`}
                  warning="Irréversible : ses runs, livrables et documents sont supprimés avec lui."
                  pending={deletion.isPending}
                  onConfirm={() => deletion.mutate(project.id)}
                />
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
