"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import type { Artifact, RunDetail } from "@/lib/api/types";

export const CHANGES_FILE = "modifications.diff";

export interface Changes {
  parent_run_id: string;
  available?: boolean;
  added?: string[];
  modified?: string[];
  removed?: string[];
  truncated?: boolean;
}

// The package step of a child run records what changed since the delivered run.
export function changesOf(run: RunDetail): Changes | null {
  const raw = run.steps.find((step) => step.name === "package")?.output?.changes;
  if (typeof raw !== "object" || raw === null) return null;
  const changes = raw as Changes;
  return typeof changes.parent_run_id === "string" ? changes : null;
}

const KINDS = [
  ["added", "Ajouté", "text-forest"],
  ["modified", "Modifié", "text-eggplant"],
  ["removed", "Supprimé", "text-coral-deep"],
] as const;

function lineClass(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---")) return "font-semibold text-navy/60";
  if (line.startsWith("@@")) return "text-navy/45";
  if (line.startsWith("+")) return "text-forest";
  if (line.startsWith("-")) return "text-coral-deep";
  return "text-navy/75";
}

function useDiffText(artifact: Artifact | undefined): { text: string | null; failed: boolean } {
  const [state, setState] = useState<{ text: string | null; failed: boolean }>({ text: null, failed: false });
  useEffect(() => {
    if (!artifact) return;
    let alive = true;
    fetch(artifact.download_url)
      .then((response) => (response.ok ? response.text() : Promise.reject(new Error(String(response.status)))))
      .then((text) => alive && setState({ text, failed: false }))
      .catch(() => alive && setState({ text: null, failed: true }));
    return () => {
      alive = false;
    };
  }, [artifact]);
  return state;
}

// What a change request changed: files by kind, then the unified diff.
export function ChangesPanel({ run, artifacts }: { run: RunDetail; artifacts: Artifact[] }) {
  const changes = changesOf(run);
  const diff = useDiffText(artifacts.find((a) => a.filename === CHANGES_FILE));
  if (!changes) return null;

  const parent = (
    <Link href={`/runs/${changes.parent_run_id}`} className="font-mono text-eggplant underline underline-offset-2">
      {changes.parent_run_id}
    </Link>
  );
  if (changes.available === false) {
    return (
      <p className="text-sm text-navy/75">
        Évolution de {parent} : les fichiers du run livré ne sont plus disponibles, aucune comparaison possible.
      </p>
    );
  }
  const files = KINDS.flatMap(([key, label, color]) => (changes[key] ?? []).map((path) => ({ path, label, color })));

  return (
    <div className="space-y-5">
      <p className="text-sm text-navy/75">
        Évolution de {parent} : {files.length === 0 ? "aucun fichier du projet n'a changé." : `${files.length} fichier(s) changé(s).`}
      </p>
      {files.length > 0 ? (
        <ul className="space-y-1">
          {files.map((file) => (
            <li key={file.path} className="flex gap-3 font-mono text-xs">
              <span className={`w-20 shrink-0 ${file.color}`}>{file.label}</span>
              <span className="break-all text-navy">{file.path}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {diff.failed ? (
        <p role="alert" className="text-sm text-coral-deep">
          Le diff n&apos;a pas pu être chargé.
        </p>
      ) : diff.text ? (
        <section aria-label="Diff" className="max-h-[560px] overflow-auto border border-navy/15 bg-cream/60 p-3">
          <pre className="font-mono text-[11px] leading-relaxed">
            {diff.text.split("\n").map((line, index) => (
              // Lines of a diff repeat: their position is their identity.
              <span key={index} className={`block whitespace-pre-wrap break-all ${lineClass(line)}`}>
                {line}
              </span>
            ))}
          </pre>
          {changes.truncated ? <p className="mt-2 text-xs text-navy/60">Diff tronqué : le ZIP contient tout le projet.</p> : null}
        </section>
      ) : null}
    </div>
  );
}
