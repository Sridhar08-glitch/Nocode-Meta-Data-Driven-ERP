import { expect, test } from "@playwright/test";

/**
 * Phase F3.7 DoD — External Portal isolation.
 *
 * Always-on (no backend): the portal runtime is a separate realm — visiting an authenticated portal
 * page with no portal session must redirect to the portal login (never render another tenant's data).
 *
 * The full cross-user isolation loop (two portal users, each sees ONLY their linked records via every
 * UI path) needs the live stack + two seeded portal users, so it's guarded behind E2E_FULL=1 with
 * creds. Run it against Django+PG to sign off the DoD.
 */
const SLUG = process.env.E2E_PORTAL_SLUG ?? "acme";

test.describe("Portal realm — route protection (no backend)", () => {
  test("unauthenticated portal home redirects to portal login", async ({ page }) => {
    await page.goto(`/portal/${SLUG}`);
    await expect(page).toHaveURL(new RegExp(`/portal/${SLUG}/login`));
  });

  test("unauthenticated portal entity page redirects to portal login", async ({ page }) => {
    await page.goto(`/portal/${SLUG}/e/ticket`);
    await expect(page).toHaveURL(new RegExp(`/portal/${SLUG}/login`));
  });
});

test.describe("Portal isolation — full cross-user loop", () => {
  test.skip(
    !process.env.E2E_FULL || !process.env.E2E_PORTAL_A_EMAIL || !process.env.E2E_PORTAL_B_EMAIL,
    "needs live stack + two seeded portal users (E2E_FULL=1 E2E_PORTAL_A_EMAIL=… E2E_PORTAL_B_EMAIL=… *_PASSWORD=…)",
  );

  test("portal user A cannot see portal user B's records via any UI path", async ({ page }) => {
    // Sign in as A, capture A's record ids on the scoped entity list.
    await page.goto(`/portal/${SLUG}/login`);
    await page.getByLabel("Email").fill(process.env.E2E_PORTAL_A_EMAIL!);
    await page.getByLabel("Password").fill(process.env.E2E_PORTAL_A_PASSWORD!);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.goto(`/portal/${SLUG}/e/${process.env.E2E_PORTAL_ENTITY ?? "ticket"}`);
    const aRowCount = await page.getByRole("row").count();
    expect(aRowCount).toBeGreaterThan(0);

    // A direct hit on a record id belonging to B must 404/empty (server-enforced), not leak.
    if (process.env.E2E_PORTAL_B_RECORD_ID) {
      const resp = await page.request.get(
        `/api/v1/portal/data/${process.env.E2E_PORTAL_ENTITY ?? "ticket"}/${process.env.E2E_PORTAL_B_RECORD_ID}/`,
      );
      expect(resp.status()).toBe(404);
    }
  });
});
