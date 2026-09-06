/**
 * Phase P0 certification — live browser automation (Playwright).
 * Verifies: existing branding renders, dark mode + theme toggle, and the per-user
 * personalization overlay (high-contrast + compact density + font-scale) applied through
 * the SAME applyBranding pipeline, on desktop and mobile. Produces before/after screenshots.
 *
 * Requires backend :8000 (sandbox/PG) + frontend :3000 running.
 * Usage: node scripts/certify_p0.mjs <email> <password> <workspaceSlug>
 */
import { chromium, devices } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = process.env.BASE || "http://localhost:3000";
const API = process.env.API || "http://localhost:8000";
const [email, password, ws] = process.argv.slice(2);
const OUT = "E:/erp/cert_p0_screenshots";
mkdirSync(OUT, { recursive: true });

const shot = (page, name) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: false });
const log = (...a) => console.log("[cert]", ...a);

// Server-side: log in via the API and set/reset this user's preferences (stored per user+workspace).
async function apiLogin() {
  const r = await fetch(`${API}/api/v1/auth/login/`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const j = await r.json();
  if (!j.access) throw new Error("api login failed: " + JSON.stringify(j).slice(0, 200));
  return j.access;
}
async function setPrefs(token, values) {
  const r = await fetch(`${API}/api/v1/me/preferences/`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, "X-Workspace-Slug": ws },
    body: JSON.stringify({ values }),
  });
  return { status: r.status, body: await r.json() };
}
async function resetPrefs(token) {
  await fetch(`${API}/api/v1/me/preferences/reset/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, "X-Workspace-Slug": ws },
    body: "{}",
  });
}

async function uiLogin(page) {
  for (let attempt = 1; attempt <= 2; attempt++) {
    await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
    await page.waitForSelector("#email", { state: "visible" });
    await page.waitForTimeout(1200); // let React hydrate so RHF captures onChange
    // Type (not raw fill) so react-hook-form's register onChange fires; verify it stuck.
    for (const [sel, val] of [["#email", email], ["#password", password]]) {
      await page.click(sel);
      await page.fill(sel, "");
      await page.type(sel, val, { delay: 15 });
      if ((await page.inputValue(sel)) !== val) {
        await page.fill(sel, val);
      }
    }
    await page.click('button[type="submit"]');
    try {
      // Next.js router.replace is a SOFT navigation → poll the pathname, not a load event.
      await page.waitForFunction(() => !location.pathname.includes("/login"), null, { timeout: 15000 });
      await page.waitForTimeout(2500); // let TenantContext resolve branding + appearance
      return;
    } catch {
      const body = await page.evaluate(() => document.body.innerText).catch(() => "");
      if (/rate|too many|429/i.test(body) && attempt === 1) {
        log("login rate-limited; waiting 62s then retrying…");
        await page.waitForTimeout(62000);
        continue;
      }
      await shot(page, "ERR_login_page");
      throw new Error("uiLogin failed; body: " + body.slice(0, 200));
    }
  }
}

async function readRootState(page) {
  return page.evaluate(() => {
    const r = document.documentElement;
    const cs = getComputedStyle(r);
    return {
      hasDark: r.classList.contains("dark"),
      hasHc: r.classList.contains("hc"),
      density: r.dataset.density || null,
      motion: r.dataset.motion || null,
      fontScale: cs.getPropertyValue("--font-scale").trim(),
      rootFontSize: cs.fontSize,
      accent: cs.getPropertyValue("--accent").trim(),
    };
  });
}

(async () => {
  const token = await apiLogin();
  await resetPrefs(token); // clean baseline
  log("api login OK; prefs reset");

  const browser = await chromium.launch();
  const results = {};

  // ---- DESKTOP ----
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await uiLogin(page);
  log("ui login OK ->", page.url());

  results.baseline = await readRootState(page);
  await shot(page, "01_desktop_baseline_light");
  log("baseline:", JSON.stringify(results.baseline));

  // Dark mode via the real ThemeToggle button.
  await page.click('button[aria-label="Toggle theme"]');
  await page.waitForTimeout(900);
  results.dark = await readRootState(page);
  await shot(page, "02_desktop_dark");
  log("dark:", JSON.stringify(results.dark));
  // back to light
  await page.click('button[aria-label="Toggle theme"]');
  await page.waitForTimeout(700);

  // Personalization overlay: set prefs server-side, reload → TenantContext applies the overlay.
  const put = await setPrefs(token, {
    high_contrast: true, density: "compact", font_scale: 130, accent: "#e11d48",
  });
  log("PUT prefs status", put.status, JSON.stringify(put.body));
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  results.personalized = await readRootState(page);
  await shot(page, "03_desktop_personalized_hc_compact_bigfont");
  log("personalized:", JSON.stringify(results.personalized));

  // Persist the authenticated session so mobile reuses it (one UI login → respects the 5/min limit).
  const storageState = await ctx.storageState();
  await ctx.close();

  // ---- MOBILE (personalization still active, no re-login) ----
  const mctx = await browser.newContext({ ...devices["Pixel 5"], storageState });
  const mpage = await mctx.newPage();
  await mpage.goto(`${BASE}/home`, { waitUntil: "domcontentloaded" });
  await mpage.waitForTimeout(2800);
  results.mobile = await readRootState(mpage);
  await shot(mpage, "04_mobile_personalized");
  log("mobile:", JSON.stringify(results.mobile));
  await mctx.close();

  await browser.close();

  // clean up so the demo workspace is left as found
  await resetPrefs(token);

  // ---- ASSERTIONS ----
  const fail = [];
  if (results.baseline.hasHc) fail.push("baseline should not be high-contrast");
  if (results.dark.hasDark !== true) fail.push("theme toggle did not enable .dark");
  if (results.personalized.hasHc !== true) fail.push("personalization did not apply .hc");
  if (results.personalized.density !== "compact") fail.push("density override not applied");
  if (results.personalized.fontScale !== "1.3") fail.push("font_scale override not applied (--font-scale)");
  if (results.mobile.hasHc !== true) fail.push("personalization not applied on mobile");

  console.log("\n=== CERT RESULT ===");
  console.log(JSON.stringify(results, null, 2));
  if (fail.length) {
    console.log("FAILURES:\n - " + fail.join("\n - "));
    process.exit(1);
  }
  console.log("ALL BROWSER ASSERTIONS PASSED");
})().catch((e) => {
  console.error("CERT ERROR:", e);
  process.exit(2);
});
