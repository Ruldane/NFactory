"use client";

import { cn } from "cn";
import { useState } from "react";

import { useFileContent, useRunFiles } from "@/lib/api/queries";
import { formatBytes } from "@/lib/format";

export function FileBrowser({ runId }: { runId: string }) {
  const files = useRunFiles(runId);
  const [selected, setSelected] = useState<string | null>(null);
  const content = useFileContent(runId, selected);

  if (files.error) {
    return <p role="alert" className="text-sm text-coral-deep">{files.error.message}</p>;
  }
  if (files.isPending) return <p className="text-sm text-navy/60">Chargement des fichiers…</p>;
  if (files.data.files.length === 0) {
    return (
      <p className="border border-dashed border-navy/25 px-6 py-8 text-center text-sm text-navy/70">
        Aucun fichier généré pour l&apos;instant.
      </p>
    );
  }
  return (
    <div className="grid gap-4 md:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
      <ul aria-label="Fichiers générés" className="max-h-[28rem] overflow-auto border border-navy/10">
        {files.data.files.map((path) => (
          <li key={path}>
            <button
              type="button"
              onClick={() => setSelected(path)}
              aria-current={path === selected ? "true" : undefined}
              className={cn(
                "w-full truncate px-3 py-1.5 text-left font-mono text-xs",
                path === selected ? "bg-eggplant text-cream" : "text-navy hover:bg-navy/5",
              )}
            >
              {path}
            </button>
          </li>
        ))}
      </ul>
      <div className="min-w-0 border border-navy/10 bg-navy/[0.03]">
        {selected === null ? (
          <p className="p-6 text-sm text-navy/60">Choisissez un fichier pour le lire.</p>
        ) : content.error ? (
          <p role="alert" className="p-6 text-sm text-coral-deep">{content.error.message}</p>
        ) : content.isPending ? (
          <p className="p-6 text-sm text-navy/60">Chargement…</p>
        ) : content.data.binary ? (
          <p className="p-6 text-sm text-navy/70">
            Fichier binaire ({formatBytes(content.data.size)}) : téléchargez le livrable pour
            l&apos;ouvrir.
          </p>
        ) : (
          <pre className="max-h-[28rem] overflow-auto p-4 font-mono text-xs leading-relaxed text-navy">
            {content.data.content}
          </pre>
        )}
      </div>
    </div>
  );
}
