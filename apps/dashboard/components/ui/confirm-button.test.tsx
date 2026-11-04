import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmButton } from "@/components/ui/confirm-button";

describe("ConfirmButton", () => {
  it("asks once more before acting", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmButton label="Supprimer" confirmLabel="Oui, supprimer" warning="Irréversible." onConfirm={onConfirm} />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Supprimer" }));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByText("Irréversible.")).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "Oui, supprimer" }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("can be called off", async () => {
    const onConfirm = vi.fn();
    render(<ConfirmButton label="Effacer" confirmLabel="Confirmer" warning="!" onConfirm={onConfirm} />);

    await userEvent.click(screen.getByRole("button", { name: "Effacer" }));
    await userEvent.click(screen.getByRole("button", { name: "Annuler" }));

    expect(screen.getByRole("button", { name: "Effacer" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Confirmer" })).toBeNull();
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
