import { expect, type Page, test } from "@playwright/test";

// The main journey of spec §3 in demo mode: describe a need, watch the run, get a tested
// deliverable, then keep it as a recipe and replay it (F38).

const RUN_URL = /\/runs\/run_[a-z0-9]+$/;
const stamp = () => new Date().toISOString().replace(/\D/g, "").slice(0, 14);

// The type cards are labels around a visually hidden radio: click the card, as a user does.
async function pickExcel(page: Page) {
  await page.getByText("Classeur Excel", { exact: true }).click();
  await expect(
    page.getByRole("radio", { name: /Classeur Excel/ }),
  ).toBeChecked();
}

async function waitUntilDelivered(page: Page) {
  // The page follows the run over SSE; "Terminé" is the COMPLETED badge (lib/run-state.ts).
  await expect(page.getByText("Terminé").first()).toBeVisible({
    timeout: 150_000,
  });
}

test("a need becomes a tested Excel workbook that can be downloaded", async ({
  page,
}) => {
  const title = `E2E dépenses ${stamp()}`;
  await page.goto("/new");
  await page
    .getByPlaceholder(/un classeur qui récapitule/)
    .fill(
      "Un classeur Excel de suivi des dépenses, avec catégorie, montant et date.",
    );
  await page.getByPlaceholder("Rapport des heures").fill(title);
  await pickExcel(page);
  await page.getByRole("button", { name: "Lancer la fabrication" }).click();

  await expect(page).toHaveURL(RUN_URL);
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await waitUntilDelivered(page);

  const workbook = page.locator("a[download]", { hasText: ".xlsx" }).first();
  await expect(workbook).toBeVisible();
  const href = await workbook.getAttribute("href");
  expect(href).toBeTruthy();
  const download = await page.request.get(href!);
  expect(download.status()).toBe(200);
  // An .xlsx is a ZIP archive: it starts with "PK".
  expect((await download.body()).subarray(0, 2).toString()).toBe("PK");
});

test("a delivered run is saved as a recipe and replayed into a new delivered run", async ({
  page,
}) => {
  const title = `E2E recette ${stamp()}`;
  await page.goto("/new");
  await page
    .getByPlaceholder(/un classeur qui récapitule/)
    .fill("Suivi des heures par semaine");
  await page.getByPlaceholder("Rapport des heures").fill(title);
  await pickExcel(page);
  await page.getByRole("button", { name: "Lancer la fabrication" }).click();
  await expect(page).toHaveURL(RUN_URL);
  const original = page.url();
  await waitUntilDelivered(page);

  await page.getByLabel("Nom de la recette").fill(title);
  await page.getByRole("button", { name: "Enregistrer comme recette" }).click();
  await expect(page.getByRole("status")).toContainText("Recette enregistrée");

  await page.goto("/recipes");
  const card = page.getByRole("article", { name: title });
  await expect(card).toContainText("Suivi des heures par semaine");
  await card.getByRole("button", { name: "Relancer" }).click();

  await expect(page).toHaveURL(RUN_URL);
  expect(page.url()).not.toBe(original);
  await waitUntilDelivered(page);
  await page.goto("/recipes");
  await expect(page.getByRole("article", { name: title })).toContainText(
    "Relancée 1 fois",
  );
});
