// Helpers for a run's trace (task 5.2): a French label per span status, and where each
// span's bar sits within the run's timeline.

import type { TraceSpan } from "@/lib/api/types";

const STATUS: Record<string, { glyph: string; label: string }> = {
  ok: { glyph: "✓", label: "Réussi" },
  error: { glyph: "✗", label: "Échec" },
  running: { glyph: "◐", label: "En cours" },
  pending: { glyph: "○", label: "En attente" },
  skipped: { glyph: "–", label: "Ignoré" },
};

export function describeSpan(status: string) {
  return STATUS[status] ?? { glyph: "?", label: status };
}

/** Left offset and width of each timed span, in percent of the whole trace. */
export function spanOffsets(spans: TraceSpan[], now: number = Date.now()) {
  const times = spans.flatMap((span) => {
    const start = span.start ? Date.parse(span.start) : NaN;
    const end = span.end ? Date.parse(span.end) : now;
    return Number.isNaN(start) ? [] : [start, end];
  });
  const offsets = new Map<string, { left: number; width: number }>();
  if (!times.length) return offsets;
  const first = Math.min(...times);
  const total = Math.max(Math.max(...times) - first, 1);
  for (const span of spans) {
    if (!span.start) continue;
    const start = Date.parse(span.start);
    const end = span.end ? Date.parse(span.end) : now;
    offsets.set(span.id, {
      left: ((start - first) / total) * 100,
      width: (Math.max(end - start, 0) / total) * 100,
    });
  }
  return offsets;
}
