import { AiNotice } from "@/components/ai-notice";
import type { Artifact } from "@/lib/api/types";
import { formatBytes } from "@/lib/format";

export function ArtifactList({ artifacts }: { artifacts: Artifact[] }) {
  if (artifacts.length === 0) {
    return (
      <p className="border border-dashed border-navy/25 px-6 py-8 text-center text-sm text-navy/70">
        Les livrables apparaissent ici à la fin du run, une fois les tests
        réussis.
      </p>
    );
  }
  return (
    <div className="space-y-3">
      <AiNotice>
        Livrables générés par IA : relisez-les et testez-les avant tout usage.
        Chaque archive contient le manifeste{" "}
        <code className="font-mono">.nfactory/provenance.json</code> (moteurs
        utilisés, empreinte de chaque fichier).
      </AiNotice>
      <ul className="grid gap-px overflow-hidden border border-navy/10 bg-navy/10 sm:grid-cols-2">
        {artifacts.map((artifact) => (
          <li key={artifact.id} className="flex flex-col gap-1 bg-cream p-4">
            <a
              href={artifact.download_url}
              download
              className="font-display text-lg text-navy underline decoration-coral/60 underline-offset-4 hover:decoration-coral-deep focus-visible:outline-2 focus-visible:outline-coral-deep"
            >
              ↓ {artifact.filename}
            </a>
            <p className="font-mono text-[11px] text-navy/55">
              {formatBytes(artifact.size)} · {artifact.checksum.slice(0, 19)}…
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
