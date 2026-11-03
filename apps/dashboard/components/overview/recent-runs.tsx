import Link from "next/link";

import { Conveyor } from "@/components/runs/conveyor";
import { StateBadge } from "@/components/runs/state-badge";
import type { RecentRun } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";

export function RecentRuns({ runs }: { runs: RecentRun[] }) {
  if (runs.length === 0) {
    return (
      <p className="border border-dashed border-navy/25 px-6 py-10 text-center text-sm text-navy/70">
        Aucun run pour l&apos;instant. Créez un projet pour lancer la première
        fabrication.
      </p>
    );
  }
  return (
    <ul className="divide-y divide-navy/10 border-y border-navy/10">
      {runs.map((run) => (
        <li
          key={run.id}
          className="grid grid-cols-1 items-center gap-3 py-4 md:grid-cols-[minmax(0,1fr)_auto_auto] md:gap-8"
        >
          <div className="min-w-0">
            <Link
              href={`/runs/${run.id}`}
              className="block truncate font-medium text-navy underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-coral-deep"
            >
              {run.project_title}
            </Link>
            <p className="font-mono text-[11px] text-navy/55">
              {run.id} · {formatDateTime(run.created_at)}
            </p>
          </div>
          <Conveyor steps={run.steps} />
          <div className="md:w-44 md:text-right">
            <StateBadge state={run.state} />
          </div>
        </li>
      ))}
    </ul>
  );
}
