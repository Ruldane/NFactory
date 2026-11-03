import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StepTimeline } from "@/components/run/step-timeline";
import type { RunStep } from "@/lib/api/types";

const step = (name: string, agent_role: string, extra: Partial<RunStep> = {}): RunStep => ({
  id: `step_${name}`,
  position: 0,
  name,
  agent_role,
  state: "SUCCEEDED",
  attempts: 1,
  output: {},
  started_at: null,
  ended_at: null,
  error: null,
  ...extra,
});

describe("StepTimeline agents", () => {
  it("names each step's agent in French, with its spec code", () => {
    render(<StepTimeline steps={[step("build", "automation")]} />);

    expect(screen.getByText("A6 · Automaticien")).toBeVisible();
  });

  it("says why a step was not run", () => {
    render(
      <StepTimeline
        steps={[
          step("architect", "architect", {
            state: "SKIPPED",
            attempts: 0,
            output: { skipped: "Aucune architecture applicative à concevoir." },
          }),
        ]}
      />,
    );

    expect(screen.getByText("Aucune architecture applicative à concevoir.")).toBeVisible();
  });
});

describe("StepTimeline repairs", () => {
  const repairs = [
    {
      attempt: 1,
      step: "tests",
      failure: "test_math : assert 3 == 2",
      cause: "Somme mal calculée",
      files: ["app/calc.py", "tests/test_calc.py"],
    },
  ];

  it("lists each automatic repair under the step it fixed", () => {
    render(<StepTimeline steps={[step("tests", "tester", { attempts: 2, output: { repairs } })]} />);

    const list = screen.getByRole("list", { name: "Corrections automatiques" });
    expect(list).toHaveTextContent("Correction 1");
    expect(list).toHaveTextContent("Somme mal calculée");
    expect(list).toHaveTextContent("app/calc.py, tests/test_calc.py");
    expect(list).toHaveTextContent("test_math : assert 3 == 2");
  });

  it("keeps the history of a step that failed after its repairs", () => {
    render(
      <StepTimeline
        steps={[
          step("tests", "tester", {
            state: "FAILED",
            error: "Échec après 1 tentative(s) de correction",
            output: { repairs },
          }),
        ]}
      />,
    );

    expect(screen.getByRole("list", { name: "Corrections automatiques" })).toBeVisible();
  });

  it("ignores a malformed history", () => {
    render(<StepTimeline steps={[step("tests", "tester", { output: { repairs: "x" } })]} />);

    expect(screen.queryByRole("list", { name: "Corrections automatiques" })).toBeNull();
  });
});
