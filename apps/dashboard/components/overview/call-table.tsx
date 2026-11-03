import type { CallMetrics } from "@/lib/api/types";
import { formatCallCost, formatLatency, formatTokens } from "@/lib/format";

interface CallTableProps<Row extends CallMetrics> {
  label: string;
  columns: { title: string; cell: (row: Row) => string }[];
  rows: Row[];
  rowKey: (row: Row) => string;
}

const TH =
  "px-3 py-2 text-left font-mono text-[11px] font-medium uppercase tracking-wider text-navy/60";
const TD = "px-3 py-2 tabular-nums";

// Model calls per engine or per agent, from the run events (spec §14.1).
export function CallTable<Row extends CallMetrics>({
  label,
  columns,
  rows,
  rowKey,
}: CallTableProps<Row>) {
  if (!rows.length) {
    return (
      <p className="text-sm text-navy/60">
        Aucun appel de modèle sur cette période.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto border border-navy/15">
      <table aria-label={label} className="w-full text-sm">
        <thead className="bg-navy/5">
          <tr>
            {columns.map((column) => (
              <th key={column.title} scope="col" className={TH}>
                {column.title}
              </th>
            ))}
            <th scope="col" className={TH}>
              Appels
            </th>
            <th scope="col" className={TH}>
              Échecs
            </th>
            <th scope="col" className={TH}>
              Latence P50
            </th>
            <th scope="col" className={TH}>
              Latence P95
            </th>
            <th scope="col" className={TH}>
              Jetons entrée / sortie
            </th>
            <th scope="col" className={TH}>
              Coût
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className="border-t border-navy/10">
              {columns.map((column) => (
                <td
                  key={column.title}
                  className="px-3 py-2 font-mono text-navy"
                >
                  {column.cell(row)}
                </td>
              ))}
              <td className={TD}>{row.calls}</td>
              <td className={TD}>{row.failures}</td>
              <td className={TD}>{formatLatency(row.latency_p50_s)}</td>
              <td className={TD}>{formatLatency(row.latency_p95_s)}</td>
              <td className={TD}>
                {formatTokens(row.input_tokens, row.output_tokens)}
              </td>
              <td className={TD}>
                {formatCallCost(row.cost_usd, row.cost_complete)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
