import { describe, expect, it } from "vitest";

import {
  formatBytes,
  formatCost,
  formatDuration,
  formatPercent,
  formatStepName,
} from "@/lib/format";

// Intl uses narrow no-break spaces in French; normalise them for readable assertions.
const plain = (s: string) => s.replace(/[  ]/g, " ");

describe("formatPercent", () => {
  it("formats a ratio as a French percentage", () => {
    expect(plain(formatPercent(2 / 3))).toBe("67 %");
  });

  it("shows a dash when the value is not measurable yet", () => {
    expect(formatPercent(null)).toBe("—");
  });
});

describe("formatDuration", () => {
  it("uses minutes and seconds", () => {
    expect(formatDuration(560)).toBe("9 min 20 s");
    expect(formatDuration(42)).toBe("42 s");
  });

  it("uses hours for long runs", () => {
    expect(formatDuration(3 * 3600 + 5 * 60)).toBe("3 h 05 min");
  });

  it("shows a dash when unknown", () => {
    expect(formatDuration(null)).toBe("—");
  });
});

describe("formatCost", () => {
  it("formats an estimate in dollars, French style", () => {
    expect(plain(formatCost(0.71))).toBe("0,71 $US");
  });

  it("says when cost is not measurable", () => {
    expect(formatCost(null)).toBe("Non mesuré");
  });
});

describe("formatStepName", () => {
  it("translates pipeline step names", () => {
    expect(formatStepName("requirements")).toBe("Besoins");
    expect(formatStepName("tests")).toBe("Tests");
  });

  it("keeps unknown names as they are", () => {
    expect(formatStepName("quantum")).toBe("quantum");
  });

  it("names every pipeline step in French", () => {
    const steps = ["checks", "docs", "package"];
    expect(steps.map(formatStepName)).toEqual(["Vérifications", "Documentation", "Livraison"]);
  });
});

describe("formatBytes", () => {
  it("uses French units", () => {
    expect(plain(formatBytes(512))).toBe("512 o");
    expect(plain(formatBytes(13_828))).toBe("13,5 Ko");
    expect(plain(formatBytes(2_500_000))).toBe("2,4 Mo");
  });
});
