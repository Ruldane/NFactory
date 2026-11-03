import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DocumentLines } from "@/components/knowledge/document-viewer";

const CONTENT = "# Licences\n\nRenouveler chaque licence.\nAvant 30 jours.\nFin.";

describe("DocumentLines", () => {
  it("numbers every line and anchors it", () => {
    const { container } = render(<DocumentLines content={CONTENT} highlight={null} />);

    expect(container.querySelector("#L3")).toHaveTextContent("Renouveler chaque licence.");
    expect(screen.getAllByRole("listitem")).toHaveLength(5);
  });

  it("highlights the cited lines", () => {
    render(<DocumentLines content={CONTENT} highlight={{ start: 3, end: 4 }} />);

    const cited = screen.getAllByRole("listitem").filter((li) => li.dataset.cited === "true");
    expect(cited.map((li) => li.id)).toEqual(["L3", "L4"]);
    expect(screen.getByText("Passage cité : lignes 3 à 4")).toBeVisible();
  });
});
