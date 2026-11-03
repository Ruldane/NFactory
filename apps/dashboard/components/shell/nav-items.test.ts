import { describe, expect, it } from "vitest";

import { isActive } from "@/components/shell/nav-items";

describe("isActive", () => {
  it("keeps a section highlighted on its sub-pages", () => {
    expect(isActive("/knowledge", "/knowledge/documents/doc_1")).toBe(true);
    expect(isActive("/projects", "/projects")).toBe(true);
  });

  it("matches whole segments only, and the overview only at the root", () => {
    expect(isActive("/new", "/newsletter")).toBe(false);
    expect(isActive("/", "/projects")).toBe(false);
    expect(isActive("/", "/")).toBe(true);
    expect(isActive("/projects", null)).toBe(false);
  });
});
