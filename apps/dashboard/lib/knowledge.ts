// Knowledge base helpers: citation links, line ranges, index status, run sources.

import type { RunDetail, SourceCitation } from "@/lib/api/types";

export function citationHref(c: { document_id: string; start_line: number; end_line: number }) {
  return `/knowledge/documents/${c.document_id}?lignes=${c.start_line}-${c.end_line}#L${c.start_line}`;
}

export function parseLines(value: string | null): { start: number; end: number } | null {
  const match = value?.match(/^(\d{1,7})(?:-(\d{1,7}))?$/);
  if (!match) return null;
  const start = Number(match[1]);
  const end = match[2] ? Number(match[2]) : start;
  return start >= 1 && end >= start ? { start, end } : null;
}

export function linesLabel(start: number, end: number): string {
  return start === end ? `ligne ${start}` : `lignes ${start} à ${end}`;
}

// Text search works as soon as a document is uploaded; vectors come from the worker.
export function indexState(doc: { chunks: number; embedded: number }) {
  const passages = `${doc.chunks} passage${doc.chunks > 1 ? "s" : ""}`;
  if (doc.embedded >= doc.chunks) return { glyph: "●", label: "Indexé", detail: passages };
  return {
    glyph: "◔",
    label: "Vecteurs en cours",
    detail: `${doc.embedded} / ${passages} · recherche plein texte prête`,
  };
}

const isCitation = (value: unknown): value is SourceCitation => {
  const v = value as Record<string, unknown> | null;
  return (
    !!v &&
    typeof v.id === "string" &&
    typeof v.document_id === "string" &&
    typeof v.path === "string" &&
    typeof v.start_line === "number" &&
    typeof v.end_line === "number"
  );
};

// null: the run had no knowledge base to search; []: it searched and found nothing.
export function sourcesOf(run: RunDetail): SourceCitation[] | null {
  const raw = run.steps.find((step) => step.name === "requirements")?.output?.sources;
  if (!Array.isArray(raw)) return null;
  return raw.filter(isCitation).map((s) => ({
    id: s.id,
    document_id: s.document_id,
    path: s.path,
    start_line: s.start_line,
    end_line: s.end_line,
    section: typeof s.section === "string" ? s.section : null,
  }));
}
