import { expect, test } from "@playwright/test";

/** Always-on UI/route-protection checks (no backend needed). */
test.describe("auth routing", () => {
  test("unauthenticated user hitting a protected route is sent to /login", async ({ page }) => {
    await page.goto("/home");
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  });

  test("root redirects to /login when signed out", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });

  test("login form validates required fields", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("Enter a valid email")).toBeVisible();
  });

  test("register surfaces the password strength meter", async ({ page }) => {
    await page.goto("/register");
    await page.getByLabel("Password").fill("weak");
    await expect(page.getByText(/Strength:/)).toBeVisible();
  });
});

/**
 * Full MVP auth flow — register → verify → login → MFA → /home — plus reuse-detection
 * logout. Requires a live backend AND a way to read the email verification token; enable
 * with E2E_FULL=1 once that harness is wired.
 */
test.describe("full auth flow", () => {
  test.skip(!process.env.E2E_FULL, "needs live backend + email-token capture (set E2E_FULL=1)");

  test("register → verify → login → land in workspace", async () => {
    // Implemented when the backend test harness exposes the verification token
    // (console-email capture or a test-only endpoint).
  });
});
