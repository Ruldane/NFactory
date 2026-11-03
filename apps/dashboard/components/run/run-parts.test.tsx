import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ArtifactList } from "@/components/run/artifact-list";
import { artifacts, runningRun } from "@/components/run/fixtures";
import { StepTimeline } from "@/components/run/step-timeline";
import { TestReport } from "@/components/run/test-report";

describe("StepTimeline", () => {
  it("lists every step with its state in words, attempts and error", () => {
    render(<StepTimeline steps={runningRun.steps} />);

    const list = screen.getByRole("list", { name: "Étapes du run" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(runningRun.steps.length);
    expect(items[0]).toHaveTextContent("Besoins");
    expect(items[0]).toHaveTextContent("Réussi");
    const tests = items[3];
    expect(tests).toHaveTextContent("Échec");
    expect(tests).toHaveTextContent("4 tentatives");
    expect(tests).toHaveTextContent("assert 1 == 2");
    expect(items[4]).toHaveTextContent("À venir");
  });
});

describe("TestReport", () => {
  it("shows the verified pytest result and each check, never an agent claim", () => {
    render(<TestReport steps={runningRun.steps} />);

    expect(screen.getByRole("group", { name: "Résultat des tests" })).toHaveTextContent("5 / 6");
    expect(screen.getByText("test_totals")).toBeVisible();
    const checks = screen.getByRole("list", { name: "Vérifications" });
    expect(within(checks).getByText("Lint (ruff)").closest("li")).toHaveTextContent("Réussi");
    expect(within(checks).getByText("Tests (pytest)").closest("li")).toHaveTextContent("Échec");
  });

  it("says when nothing has run yet", () => {
    render(<TestReport steps={[]} />);
    expect(screen.getByText(/Aucune vérification exécutée/)).toBeVisible();
  });
});

describe("ArtifactList", () => {
  it("offers each deliverable for download with its size", () => {
    render(<ArtifactList artifacts={artifacts} />);

    const link = screen.getByRole("link", { name: /rapport-des-heures\.xlsx/ });
    expect(link).toHaveAttribute("href", "/api/v1/artifacts/art_1/download");
    expect(link.closest("li")).toHaveTextContent(/8,8\sKo/);
  });

  it("explains that deliverables come at the end", () => {
    render(<ArtifactList artifacts={[]} />);
    expect(screen.getByText(/Les livrables apparaissent ici/)).toBeVisible();
  });
});
