import { describe, expect, it } from "vitest";

import { citationHref, indexState, linesLabel, parseLines, sourcesOf } from "@/lib/knowledge";
import type { RunDetail } from "@/lib/api/types";

describe("citationHref", () => {
  it("points at the document viewer, on the cited lines", () => {
    expect(citationHref({ document_id: "doc_1", start_line: 4, end_line: 9 })).toBe(
      "/knowledge/documents/doc_1?lignes=4-9#L4",
    );
  });
});

describe("parseLines", () => {
  it("reads a line range and refuses anything else", () => {
    expect(parseLines("4-9")).toEqual({ start: 4, end: 9 });
    expect(parseLines("7")).toEqual({ start: 7, end: 7 });
    expect(parseLines("9-4")).toBeNull();
    expect(parseLines("abc")).toBeNull();
    expect(parseLines(null)).toBeNull();
  });
});

describe("linesLabel", () => {
  it("says one line or a range in French", () => {
    expect(linesLabel(3, 3)).toBe("ligne 3");
    expect(linesLabel(3, 8)).toBe("lignes 3 à 8");
  });
});

describe("indexState", () => {
  it("never claims vectors that are not computed yet", () => {
    expect(indexState({ chunks: 4, embedded: 4 })).toEqual({
      glyph: "●",
      label: "Indexé",
      detail: "4 passages",
    });
    expect(indexState({ chunks: 4, embedded: 1 })).toEqual({
      glyph: "◔",
      label: "Vecteurs en cours",
      detail: "1 / 4 passages · recherche plein texte prête",
    });
  });
});

describe("sourcesOf", () => {
  const run = (output: Record<string, unknown>) =>
    ({ steps: [{ name: "requirements", output }] }) as unknown as RunDetail;

  it("reads the cited sources defensively", () => {
    const sources = sourcesOf(
      run({
        sources: [
          { id: "S1", document_id: "doc_1", path: "a.md", start_line: 1, end_line: 3, section: "A" },
          { id: "S2", path: "broken" },
        ],
      }),
    );

    expect(sources).toEqual([
      { id: "S1", document_id: "doc_1", path: "a.md", start_line: 1, end_line: 3, section: "A" },
    ]);
  });

  it("tells a run without knowledge base apart from one that found nothing", () => {
    expect(sourcesOf(run({}))).toBeNull();
    expect(sourcesOf(run({ sources: [] }))).toEqual([]);
  });
});
