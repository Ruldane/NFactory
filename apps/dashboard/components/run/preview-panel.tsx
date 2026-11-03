"use client";

import { Button } from "@/components/ui/button";
import { usePreview, useStartPreview, useStopPreview } from "@/lib/api/queries";
import type { RunDetail } from "@/lib/api/types";

// A completed run whose recipe declared how to run the app (package step output).
export function hasPreview(run: RunDetail): boolean {
  if (run.state !== "COMPLETED") return false;
  const output = run.steps.find((step) => step.name === "package")?.output;
  return typeof output?.preview === "object" && output.preview !== null;
}

const minutes = (seconds: number | null) => (seconds === null ? null : Math.max(1, Math.round(seconds / 60)));

// Live preview: the generated app runs in the sandbox (no Internet, read-only workspace)
// and is framed from the preview gateway, another origin than the dashboard.
export function PreviewPanel({ runId }: { runId: string }) {
  const preview = usePreview(runId);
  const start = useStartPreview(runId);
  const stop = useStopPreview(runId);
  const error = start.error ?? stop.error ?? preview.error;
  const current = preview.data;
  const left = minutes(current?.expires_in_s ?? null);

  return (
    <div className="space-y-3">
      <p className="text-sm text-navy/75">
        L&apos;application générée tourne dans le sandbox : sans accès à Internet ni à NFactory, avec ses
        propres données de test, effacées à l&apos;arrêt.
      </p>
      {error ? (
        <p role="alert" className="text-sm text-coral-deep">
          {error.message}
        </p>
      ) : null}
      {current?.running && current.url ? (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="outline" size="sm" onClick={() => stop.mutate()} disabled={stop.isPending}>
              Arrêter l&apos;aperçu
            </Button>
            <a
              href={current.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-[11px] text-eggplant underline underline-offset-2"
            >
              Ouvrir dans un onglet ↗
            </a>
            {left !== null ? (
              <span className="font-mono text-[11px] text-navy/60">s&apos;arrête dans {left} min</span>
            ) : null}
          </div>
          <iframe
            title="Aperçu de l'application générée"
            src={current.url}
            sandbox="allow-scripts allow-forms allow-same-origin"
            referrerPolicy="no-referrer"
            className="h-[560px] w-full rounded-sm border border-navy/20 bg-white"
          />
        </>
      ) : (
        <Button onClick={() => start.mutate()} disabled={start.isPending || preview.isPending}>
          {start.isPending ? "Démarrage…" : "Lancer l'aperçu"}
        </Button>
      )}
    </div>
  );
}
