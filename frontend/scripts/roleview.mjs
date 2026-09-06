/**
 * Log in as a specific user and capture what their role sees:
 * the sidebar nav links + a screenshot + spot-checks on gated pages.
 *
 *   node scripts/roleview.mjs <email> <password> <slug> <roleLabel>
 */
import { chromium } from "@playwright/test";

const [, , email, password, slug, roleLabel = "role"] = process.argv;
const BASE = "http://localhost:3000";
const OUT = `E:/erp/docs/screenshots/roles`;

const b = await chromium.launch({ headless: !process.env.HEADED, slowMo: process.env.HEADED ? 150 : 0 });
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();
await p.goto(BASE + "/login", { waitUntil: "networkidle" });
await p.fill('input[type="email"]', email);
await p.fill('input[type="password"]', password);
await p.click('button[type="submit"]');
await p.waitForTimeout(2500);
if (slug) {
  await p.evaluate((s) => localStorage.setItem("nexus.ws", s), slug);
  await p.goto(BASE + "/home", { waitUntil: "networkidle" });
  await p.waitForTimeout(4000);
}

const links = await p.$$eval('nav[aria-label="Primary"] a', (as) => as.map((a) => a.textContent.trim()));
console.log(`ROLE: ${roleLabel}  (${email})`);
console.log("SIDEBAR LINKS (" + links.length + "):", JSON.stringify(links));
await p.screenshot({ path: `${OUT}/${roleLabel}-nav.png`, fullPage: true });

// spot-check: can this role open admin / permissions / studio pages, or are they blocked?
for (const [path, name] of [["/admin", "admin"], ["/permissions", "permissions"], ["/studio", "studio"], ["/workflows", "workflows"], ["/e/student", "students"], ["/e/teacher", "teachers"]]) {
  await p.goto(BASE + path, { waitUntil: "networkidle" }).catch(() => {});
  await p.waitForTimeout(1500);
  const url = p.url();
  const bodyText = (await p.locator("main, body").first().innerText().catch(() => "")).slice(0, 400).replace(/\s+/g, " ");
  const denied = /permission|denied|not allowed|forbidden|can.?t|no access|unauthor/i.test(bodyText);
  console.log(`  ${name.padEnd(12)} -> ${url.replace(BASE, "")} ${denied ? "[DENIED/empty]" : "[visible]"}`);
  await p.screenshot({ path: `${OUT}/${roleLabel}-${name}.png`, fullPage: true });
}
await b.close();
