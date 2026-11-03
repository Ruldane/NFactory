import type { RunStep } from "@/lib/api/types";

export type Repair = {
  attempt: number;
  failure: string;
  cause: string;
  files: string[];
};

const isRepair = (value: unknown): value is Repair => {
  if (typeof value !== "object" || value === null) return false;
  const r = value as Record<string, unknown>;
  return typeof r.attempt === "number" && typeof r.cause === "string" && Array.isArray(r.files);
};

// The worker stores each applied patch in the step output (`repairs`).
export function repairsOf(step: RunStep): Repair[] {
  const raw = step.output?.repairs;
  return Array.isArray(raw) ? raw.filter(isRepair) : [];
}

// Automatic repairs of a step: what failed, the diagnosis, and the files changed.
export function RepairList({ repairs }: { repairs: Repair[] }) {
  if (repairs.length === 0) return null;
  return (
    <ol aria-label="Corrections automatiques" className="mt-1.5 space-y-1.5 border-l-2 border-eggplant/40 pl-2">
      {repairs.map((repair) => (
        <li key={repair.attempt} className="text-xs text-navy/75">
          <p>
            <span className="font-mono text-[11px] text-eggplant">Correction {repair.attempt}</span>{" "}
            {repair.cause}
          </p>
          <p className="font-mono text-[11px] break-all text-navy/60">{repair.files.join(", ")}</p>
          {repair.failure ? (
            <p className="line-clamp-2 font-mono text-[11px] text-navy/45" title={repair.failure}>
              {repair.failure}
            </p>
          ) : null}
        </li>
      ))}
    </ol>
  );
}
