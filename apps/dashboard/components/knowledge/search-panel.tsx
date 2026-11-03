"use client";

import Link from "next/link";
import { type FormEvent, useId, useState } from "react";

import { ALERT, FIELD, PRIMARY } from "@/components/ui/form-styles";
import { useKnowledgeSearch } from "@/lib/api/knowledge";
import type { KnowledgeHit } from "@/lib/api/types";
import { citationHref, linesLabel } from "@/lib/knowledge";

const MATCHED: Record<string, string> = {
  "text,vector": "plein texte + vecteurs",
  text: "plein texte",
  vector: "vecteurs",
};

export function SearchPanel() {
  const inputId = useId();
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const search = useKnowledgeSearch(query, null);

  function submit(event: FormEvent) {
    event.preventDefault();
    setQuery(draft.trim());
  }

  return (
    <section aria-labelledby="search-title" className="space-y-5">
      <h2 id="search-title" className="font-display text-2xl text-navy">
        Rechercher
      </h2>
      <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row">
        <label htmlFor={inputId} className="sr-only">
          Rechercher dans la base
        </label>
        <input
          id={inputId}
          type="search"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ex. : quand renouveler les licences ?"
          maxLength={500}
          className={`${FIELD} text-base`}
        />
        <button type="submit" className={PRIMARY} disabled={!draft.trim()}>
          Rechercher
        </button>
      </form>
      {search.error ? <p role="alert" className={ALERT}>{search.error.message}</p> : null}
      {search.data ? (
        <div className="space-y-3">
          {search.data.engine.used ? null : (
            <p className="text-sm text-navy/70">
              Recherche sans vecteurs : {search.data.engine.error ?? "moteur indisponible"}
            </p>
          )}
          {search.data.hits.length === 0 ? (
            <p className="text-sm text-navy/70">Aucun passage ne correspond.</p>
          ) : (
            <ol className="space-y-3">
              {search.data.hits.map((hit) => (
                <HitCard key={hit.chunk_id} hit={hit} />
              ))}
            </ol>
          )}
        </div>
      ) : null}
    </section>
  );
}

function HitCard({ hit }: { hit: KnowledgeHit }) {
  const where = [hit.section, hit.symbol, hit.page ? `page ${hit.page}` : null].filter(Boolean).join(" · ");
  return (
    <li className="border-l-4 border-navy/20 bg-cream/60 py-3 pl-4 pr-3 hover:border-coral-deep">
      <Link href={citationHref(hit)} className="font-mono text-xs text-coral-deep hover:underline">
        {hit.path} · {linesLabel(hit.start_line, hit.end_line)}
      </Link>
      {where ? <p className="text-xs text-navy/60">{where}</p> : null}
      <p className="mt-2 line-clamp-4 whitespace-pre-wrap text-sm text-navy">{hit.content}</p>
      <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-navy/50">
        trouvé par {MATCHED[[...hit.matched].sort().join(",")] ?? "—"}
      </p>
    </li>
  );
}
