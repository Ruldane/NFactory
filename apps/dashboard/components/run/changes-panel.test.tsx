import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChangesPanel, changesOf } from "@/components/run/changes-panel";
import { completedRun } from "@/components/run/fixtures";
import type { Artifact, RunDetail } from "@/lib/api/types";

const PATCH = "--- a/app/models.py\n+++ b/app/models.py\n@@ -1,2 +1,3 @@\n name\n-city\n+city\n+departement\n";

const child = (changes: unknown): RunDetail => ({
  ...completedRun,
  parent_run_id: "run_parent",
  steps: completedRun.steps.map((s) => (s.name === "package" ? { ...s, output: { changes } } : s)),
});

const diffArtifact: Artifact = {
  id: "art_d",
  filename: "modifications.diff",
  mime: "text/x-diff",
  size: PATCH.length,
  checksum: "sha256:x",
  created_at: "2026-11-01T10:01:30Z",
  download_url: "/api/v1/artifacts/art_d/download",
};

afterEach(() => vi.unstubAllGlobals());

describe("ChangesPanel", () => {
  it("lists the changed files and shows the diff", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(PATCH, { status: 200 })));
    const run = child({ parent_run_id: "run_parent", added: ["app/export.py"], modified: ["app/models.py"], removed: [], truncated: false });

    render(<ChangesPanel run={run} artifacts={[diffArtifact]} />);

    expect(screen.getByRole("link", { name: "run_parent" })).toHaveAttribute("href", "/runs/run_parent");
    expect(screen.getByText("app/export.py")).toBeVisible();
    expect(screen.getByText("Ajouté")).toBeVisible();
    expect(screen.getByText("Modifié")).toBeVisible();
    const diff = await screen.findByRole("region", { name: "Diff" });
    expect(diff).toHaveTextContent("+departement");
    expect(screen.getByText("+departement")).toHaveClass("text-forest");
    expect(screen.getByText("-city")).toHaveClass("text-coral-deep");
  });

  it("says when the delivered run's files are gone", () => {
    render(<ChangesPanel run={child({ parent_run_id: "run_parent", available: false })} artifacts={[]} />);

    expect(screen.getByText(/fichiers du run livré ne sont plus disponibles/)).toBeVisible();
  });
});

describe("changesOf", () => {
  it("reads the package step's changes, if any", () => {
    expect(changesOf(completedRun)).toBeNull();
    expect(changesOf(child({ parent_run_id: "run_parent", available: false }))?.parent_run_id).toBe("run_parent");
  });
});
