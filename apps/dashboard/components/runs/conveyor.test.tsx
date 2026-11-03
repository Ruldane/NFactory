import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Conveyor } from "@/components/runs/conveyor";
import type { StepBrief } from "@/lib/api/types";

const steps: StepBrief[] = [
  { name: "requirements", agent_role: "requirements", state: "SUCCEEDED", attempts: 1 },
  { name: "tests", agent_role: "tester", state: "FAILED", attempts: 4 },
  { name: "review", agent_role: "reviewer", state: "SKIPPED", attempts: 0 },
];

describe("Conveyor", () => {
  it("renders one labelled station per step, in order", () => {
    render(<Conveyor steps={steps} />);

    const list = screen.getByRole("list", { name: "Étapes du run" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveAccessibleName("Besoins : Réussi");
  });

  it("states the failure and the repair attempts in words, not only color", () => {
    render(<Conveyor steps={steps} />);

    expect(screen.getByRole("listitem", { name: "Tests : Échec (4 tentatives)" })).toBeVisible();
    expect(screen.getByRole("listitem", { name: "Revue : Non exécuté" })).toHaveTextContent("–");
  });
});
