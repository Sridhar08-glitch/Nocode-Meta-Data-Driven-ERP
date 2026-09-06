import { expect, test, type Page } from "@playwright/test";

/**
 * B0.2 — System-Entity Adapter through the Generic Runtime.
 *
 * Proves native-model engines (Treasury + Inventory) render through the EXISTING `/e/[entity]` runtime
 * — list → detail → create — with NO bespoke pages. The live loop needs the full stack + seeded creds,
 * so it is guarded behind E2E_FULL=1 (E2E_EMAIL / E2E_PASSWORD). The always-on block covers route
 * protection with no backend.
 */

// ── always-on: the runtime routes for system entities are auth-guarded ────────────────
test.describe("system-entity route protection (no backend)", () => {
  for (const path of ["/e/treasury_facility", "/e/inventory_item"]) {
    test(`unauthenticated ${path} → /login`, async ({ page }) => {
      await page.goto(path);
      await expect(page).toHaveURL(/\/login/);
    });
  }
});

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(process.env.E2E_EMAIL!);
  await page.getByLabel("Password").fill(process.env.E2E_PASSWORD!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/home/);
}

/** List → New → create → back to list, for one system entity, through the generic runtime. */
async function renderEngine(page: Page, slug: string, createLabelField: string, value: string) {
  await page.goto(`/e/${slug}`);
  // the generic list renders the system entity's plural name + a New button
  await expect(page.getByRole("button", { name: "New" })).toBeVisible();
  await page.getByRole("button", { name: "New" }).click();
  await expect(page).toHaveURL(new RegExp(`/e/${slug}/new`));
  // the generic form renderer built the create form from the B0 descriptor
  await page.getByLabel(createLabelField).fill(value);
  await page.getByRole("button", { name: /Create|Save/ }).click();
  // back on the list, the new row is visible in the generic DataTable
  await expect(page).toHaveURL(new RegExp(`/e/${slug}`));
  await expect(page.getByText(value)).toBeVisible();
}

test.describe("B0.2 — native engines render through the Generic Runtime", () => {
  test.skip(
    !process.env.E2E_FULL || !process.env.E2E_EMAIL || !process.env.E2E_PASSWORD,
    "needs live stack + creds (E2E_FULL=1 E2E_EMAIL=… E2E_PASSWORD=…)",
  );

  test("Treasury (finance) renders + creates through /e/[entity]", async ({ page }) => {
    await signIn(page);
    await renderEngine(page, "treasury_counterparty", "Code", `CP-${Date.now()}`);
  });

  test("Inventory (ops) renders + creates through the SAME runtime", async ({ page }) => {
    await signIn(page);
    await renderEngine(page, "inventory_item", "Sku", `SKU-${Date.now()}`);
  });
});
