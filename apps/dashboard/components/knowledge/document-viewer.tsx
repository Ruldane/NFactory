"use client";

import { cn } from "cn";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { useDocument } from "@/lib/api/knowledge";
import { formatDateTime } from "@/lib/format";
import { indexState, linesLabel, parseLines } from "@/lib/knowledge";

// A cited document, line by line: the cited range is highlighted and scrolled to.
export function DocumentViewer({ documentId }: { documentId: string }) {
  const document = useDocument(documentId);
  const highlight = parseLines(useSearchParams().get("lignes"));

  if (document.error) {
    return (
      <p role="alert" className="border-l-4 border-coral-deep bg-coral-deep/8 px-5 py-4 text-sm">
        {document.error.message}
      </p>
    );
  }
  if (document.isPending) {
    return <Skeleton className="h-96 bg-navy/8" aria-label="Chargement du document" />;
  }
  const doc = document.data;
  const state = indexState(doc);
  return (
    <article className="space-y-6">
      <header className="nf-rise space-y-2">
        <Link href="/knowledge" className="font-mono text-[11px] uppercase tracking-[0.2em] text-coral-deep hover:underline">
          ← Base de connaissances
        </Link>
        <h1 className="break-all font-display text-4xl text-navy">{doc.path}</h1>
        <p className="font-mono text-xs text-navy/60">
          {doc.kind ?? "—"} · révision {doc.revision ?? "—"} · importé le {formatDateTime(doc.created_at)} ·{" "}
          <span aria-hidden>{state.glyph}</span> {state.label}
        </p>
      </header>
      <DocumentLines content={doc.content} highlight={highlight} />
    </article>
  );
}

export function DocumentLines({
  content,
  highlight,
}: {
  content: string;
  highlight: { start: number; end: number } | null;
}) {
  const first = useRef<HTMLLIElement>(null);
  useEffect(() => {
    first.current?.scrollIntoView?.({ block: "center" });
  }, [highlight?.start]);
  const lines = content.replace(/\n$/, "").split("\n");
  const cited = (n: number) => !!highlight && n >= highlight.start && n <= highlight.end;

  return (
    <div className="nf-rise [animation-delay:80ms]">
      {highlight ? (
        <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.2em] text-coral-deep">
          Passage cité : {linesLabel(highlight.start, highlight.end)}
        </p>
      ) : null}
      <ol className="overflow-x-auto border border-navy/15 bg-cream py-3 font-mono text-[13px] leading-6 text-navy">
        {lines.map((line, index) => {
          const number = index + 1;
          return (
            <li
              key={number}
              id={`L${number}`}
              ref={highlight && number === highlight.start ? first : undefined}
              data-cited={cited(number) ? "true" : undefined}
              className={cn(
                "grid grid-cols-[4rem_1fr] gap-4 pr-4",
                cited(number) && "border-l-4 border-coral-deep bg-butter/60",
              )}
            >
              <a
                href={`#L${number}`}
                className="select-none text-right text-navy/40 hover:text-coral-deep"
                aria-label={`Ligne ${number}`}
              >
                {number}
              </a>
              <span className="whitespace-pre-wrap break-words">{line || " "}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
