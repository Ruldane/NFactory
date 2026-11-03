import { expect, test } from "@playwright/test";

// Governance journeys (task 5.4): settings changes are audited, the approval center lists
// what waits, and the overview says its data is demo data.

test("the overview shows measured figures and flags demo data", async ({
  page,
}) => {
  await page.goto("/");

  await expect(page.getByText("Données de démonstration")).toBeVisible();
  await expect(page.getByText("Validations en attente")).toBeVisible();
});

test("a change of run limits appears in the audit journal", async ({
  page,
}) => {
  await page.goto("/settings");
  const calls = page.getByLabel("Appels IA par run");
  const current = Number(await calls.inputValue());
  // Moves between two values so repeated runs keep the workspace usable.
  const next = current === 80 ? 81 : 80;
  await calls.fill(String(next));
  await page.getByRole("button", { name: "Enregistrer les limites" }).click();
  await expect(page.getByRole("status")).toContainText("Limites enregistrées");

  await page.goto("/audit");
  const journal = page.getByRole("table", { name: "Journal d'audit" });
  const latest = journal.getByRole("row").nth(1);
  await expect(latest).toContainText("Limites des runs modifiées");
  await expect(latest).toContainText("Moi (local)");
  await expect(page.getByText(/Votre rôle dans .* Propriétaire/)).toBeVisible();
});

test("the approval center lists pending decisions with a way to the run", async ({
  page,
}) => {
  await page.goto("/audit");
  const empty = page.getByText("Aucune décision en attente.");
  const pending = page.getByRole("article").first();
  await expect(empty.or(pending)).toBeVisible();

  // A fresh stack has nothing waiting: the center then says so instead of listing.
  if (await empty.isVisible()) return;
  await pending.getByRole("link", { name: /Ouvrir le run/ }).click();
  await expect(page).toHaveURL(/\/runs\/run_/);
});
