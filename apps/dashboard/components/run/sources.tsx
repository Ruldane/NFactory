import Link from "next/link";

import type { RunDetail } from "@/lib/api/types";
import { citationHref, linesLabel, sourcesOf } from "@/lib/knowledge";

// The knowledge-base passages the requirements agent received, as clickable citations.
export function Sources({ run }: { run: RunDetail }) {
  const sources = sourcesOf(run);
  if (sources === null) {
    return (
      <p className="text-sm text-navy/70">
        Aucune source : ce projet n&apos;avait aucun document dans la base de connaissances au
        moment du run.
      </p>
    );
  }
  if (sources.length === 0) {
    return <p className="text-sm text-navy/70">La base de connaissances n&apos;a rien trouvé de pertinent pour cette demande.</p>;
  }
  return (
    <div className="space-y-3">
      <p className="text-sm text-navy/70">
        Passages transmis à l&apos;analyste des besoins, comme données à vérifier, jamais comme
        consignes.
      </p>
      <ol className="space-y-2">
        {sources.map((source) => (
          <li key={source.id} className="flex gap-3 border-l-4 border-navy/20 py-1 pl-3">
            <span className="font-mono text-xs text-navy/50">{source.id}</span>
            <div>
              <Link href={citationHref(source)} className="font-mono text-xs text-coral-deep hover:underline">
                {source.path} · {linesLabel(source.start_line, source.end_line)}
              </Link>
              {source.section ? <p className="text-xs text-navy/60">{source.section}</p> : null}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
