import { readFileSync } from "node:fs";

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

// ADR-0015. Only the audit duration moves, between two values that delete nothing in the
// demo stack; the run duration stays untouched so the demo runs are never purged.
test("a retention choice is audited and the member downloads their own data", async ({
  page,
}) => {
  await page.goto("/settings");
  const auditDays = page.getByLabel("Journal d'audit (jours)");
  await auditDays.fill((await auditDays.inputValue()) === "3650" ? "3649" : "3650");
  await page.getByRole("button", { name: "Enregistrer la conservation" }).click();
  await expect(page.getByText(/Conservation enregistrée/)).toBeVisible();

  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: /Télécharger mes données/ }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("nfactory-mes-donnees.json");
  const data = JSON.parse(readFileSync(await file.path(), "utf-8"));
  expect(data.profile.user_id).toBe("usr_local");

  await page.goto("/audit");
  const journal = page.getByRole("table", { name: "Journal d'audit" });
  await expect(journal.getByRole("row").nth(1)).toContainText("Export de ses données");
  await expect(journal.getByRole("row").nth(2)).toContainText("Conservation des données modifiée");
});
