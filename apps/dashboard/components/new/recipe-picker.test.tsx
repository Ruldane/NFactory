import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RecipePicker } from "@/components/new/recipe-picker";
import type { Recipe } from "@/lib/api/types";

const recipes: Recipe[] = [
  {
    kind: "python-api",
    project_type: "api",
    label: "API Python",
    description: "API REST testée",
    deliverable: "code",
    outputs: ["ZIP"],
    phase: 1,
    available: true,
  },
  {
    kind: "excel-automation",
    project_type: "excel",
    label: "Classeur Excel",
    description: "Classeur avec formules",
    deliverable: "non-code",
    outputs: [".xlsx"],
    phase: 1,
    available: true,
  },
  {
    kind: "webapp-react-fastapi",
    project_type: "webapp",
    label: "Application web",
    description: "React + FastAPI",
    deliverable: "code",
    outputs: ["ZIP"],
    phase: 3,
    available: false,
  },
];

describe("RecipePicker", () => {
  it("lets the user pick an available type", async () => {
    const onChange = vi.fn();
    render(<RecipePicker recipes={recipes} value="api" onChange={onChange} />);

    expect(screen.getByRole("radio", { name: /API Python/ })).toBeChecked();
    await userEvent.click(screen.getByRole("radio", { name: /Classeur Excel/ }));
    expect(onChange).toHaveBeenCalledWith("excel");
  });

  it("shows planned types as disabled, with their phase and the deliverable kind", () => {
    render(<RecipePicker recipes={recipes} value="api" onChange={vi.fn()} />);

    const webapp = screen.getByRole("radio", { name: /Application web/ });
    expect(webapp).toBeDisabled();
    expect(webapp).toHaveAccessibleName(/Phase 3/);
    expect(screen.getByRole("radio", { name: /Classeur Excel/ })).toHaveAccessibleName(/Non-code/);
  });
});
