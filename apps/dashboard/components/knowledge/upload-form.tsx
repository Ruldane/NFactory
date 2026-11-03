"use client";

import { type FormEvent, useId, useState } from "react";

import { ALERT, FIELD, KICKER, PRIMARY } from "@/components/ui/form-styles";
import { useUploadDocument } from "@/lib/api/knowledge";
import { useProjects } from "@/lib/api/queries";

const ACCEPT = ".md,.markdown,.txt,.rst,.csv,.pdf,.docx,.py,.js,.jsx,.ts,.tsx,.ps1,.psm1,.sh,.sql,.go,.rs,.java,.cs,.rb,.php,.yaml,.yml,.toml,.json,.css,.html";

export function UploadForm() {
  const ids = { file: useId(), scope: useId() };
  const projects = useProjects(null);
  const upload = useUploadDocument();
  const [file, setFile] = useState<File | null>(null);
  const [projectId, setProjectId] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    if (file) upload.mutate({ file, projectId: projectId || null });
  }

  const result = upload.data;
  return (
    <form onSubmit={submit} className="grid gap-4 border border-navy/15 bg-cream/60 p-5 md:grid-cols-[1fr_16rem_auto] md:items-end">
      <div className="space-y-1">
        <label htmlFor={ids.file} className={KICKER}>
          Fichier à importer
        </label>
        <input
          id={ids.file}
          type="file"
          accept={ACCEPT}
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            upload.reset();
          }}
          className={`${FIELD} file:mr-3 file:border-0 file:bg-navy/10 file:px-2 file:py-1 file:font-mono file:text-xs`}
        />
      </div>
      <div className="space-y-1">
        <label htmlFor={ids.scope} className={KICKER}>
          Portée
        </label>
        <select id={ids.scope} value={projectId} onChange={(e) => setProjectId(e.target.value)} className={FIELD}>
          <option value="">Tout l&apos;espace</option>
          {(projects.data?.items ?? []).map((project) => (
            <option key={project.id} value={project.id}>
              {project.title}
            </option>
          ))}
        </select>
      </div>
      <button type="submit" className={PRIMARY} disabled={!file || upload.isPending}>
        {upload.isPending ? "Import…" : "Importer"}
      </button>
      {upload.error ? (
        <p role="alert" className={`${ALERT} md:col-span-3`}>
          {upload.error.message}
        </p>
      ) : null}
      {result ? (
        <p role="status" className="font-mono text-xs text-forest md:col-span-3">
          ✓{" "}
          {result.duplicate
            ? `${result.path} : déjà présent, rien n'a été réindexé.`
            : `${result.path} importé${result.replaced ? " (remplace la révision précédente)" : ""} : ${result.chunks} passages, recherche plein texte prête, vecteurs en cours.`}
        </p>
      ) : null}
    </form>
  );
}
