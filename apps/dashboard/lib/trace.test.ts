import { describe, expect, it } from "vitest";

import type { TraceSpan } from "@/lib/api/types";
import { describeSpan, spanOffsets } from "@/lib/trace";

const span = (id: string, start: string | null, end: string | null): TraceSpan => ({
  id,
  parent_id: null,
  kind: "step",
  name: id,
  start,
  end,
  duration_s: null,
  status: "ok",
});

describe("spanOffsets", () => {
  it("places each bar by its start and length within the whole trace", () => {
    const offsets = spanOffsets([
      span("run", "2026-11-01T10:00:00Z", "2026-11-01T10:00:10Z"),
      span("late", "2026-11-01T10:00:05Z", "2026-11-01T10:00:07Z"),
      span("never", null, null),
    ]);

    expect(offsets.get("run")).toEqual({ left: 0, width: 100 });
    expect(offsets.get("late")).toEqual({ left: 50, width: 20 });
    expect(offsets.has("never")).toBe(false);
  });

  it("draws a span still running up to now", () => {
    const now = Date.parse("2026-11-01T10:00:04Z");
    const offsets = spanOffsets([span("busy", "2026-11-01T10:00:00Z", null)], now);

    expect(offsets.get("busy")).toEqual({ left: 0, width: 100 });
  });
});

describe("describeSpan", () => {
  it("gives every status a glyph and a French label", () => {
    for (const status of ["ok", "error", "running", "pending", "skipped"]) {
      expect(describeSpan(status).label).not.toBe(status);
    }
  });
});
