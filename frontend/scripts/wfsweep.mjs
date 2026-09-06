/**
 * Trigger every School workflow through the UI and report which fired/completed.
 * For record_created workflows: create a record of the entity.
 * For record_updated workflows: create then set the record's status to the condition value.
 *
 *   node scripts/wfsweep.mjs <slug> <ownerEmail> <ownerPw>
 */
import { chromium } from "@playwright/test";
import fs from "node:fs";

const [, , SLUG, EMAIL, PW] = process.argv;
const BASE = "http://localhost:3000";
const WFS = JSON.parse(fs.readFileSync("E:/erp/_wf_list.json", "utf8"));
const log = (...a) => console.log("[sweep]", ...a);

async function login(page) {
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', EMAIL);
  await page.fill('input[type="password"]', PW);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2500);
  await page.evaluate((s) => localStorage.setItem("nexus.ws", s), SLUG);
  await page.goto(BASE + "/home", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
}

// minimal generic form fill: first text field = a name, selects = first option, toggles left
async function fillForm(page, i) {
  const form = page.locator("form").first();
  if (!(await form.count())) return false;
  const texts = await form.locator('input[type="text"]:visible, input:not([type]):visible, input[type="email"]:visible, input[type="tel"]:visible, textarea:visible').all();
  let first = true;
  for (const t of texts) {
    const type = (await t.getAttribute("type")) || "text";
    const v = type === "email" ? `demo${i}@ex.com` : type === "tel" ? `+1-555-${1000 + i}` : `WF Demo ${i}`;
    await t.fill(v).catch(() => {});
    first = false;
  }
  void first;
  // date inputs
  for (const d of await form.locator('input[type="date"]:visible').all()) await d.fill("2026-06-15").catch(() => {});
  for (const n of await form.locator('input[type="number"]:visible').all()) await n.fill(String((i % 30) + 1)).catch(() => {});
  // selects: pick first option (skip; leave status for explicit set)
  for (const cb of await form.locator('button[role="combobox"]:visible').all()) {
    try { await cb.click({ timeout: 1200 }); await page.waitForTimeout(300); await page.locator('[role="option"]:visible').first().click({ timeout: 1200 }).catch(() => {}); await page.keyboard.press("Escape").catch(() => {}); } catch { /* noop */ }
  }
  const submit = form.locator('button[type="submit"], button:has-text("Create"), button:has-text("Save")').first();
  if (!(await submit.count())) return false;
  await submit.click({ timeout: 3000 }).catch(() => {});
  await page.waitForTimeout(1200);
  return !page.url().includes("/new");
}

// set the Status select on the edit form to a specific value, then save
async function setStatus(page, url, value) {
  const editUrl = url.replace(/\/$/, "") + "/edit";
  await page.goto(editUrl, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  try {
    // the Status combobox — try aria-label first, else the last combobox
    let combo = page.locator('button[role="combobox"][aria-label="Status"]');
    if (!(await combo.count())) combo = page.locator('button[role="combobox"]').last();
    await combo.click({ timeout: 2000 });
    await page.waitForTimeout(300);
    const opt = page.locator(`[role="option"]:has-text("${value}")`).first();
    if (await opt.count()) await opt.click({ timeout: 2000 });
    else { await page.keyboard.press("Escape"); return false; }
    await page.locator('form button[type="submit"], button:has-text("Save")').first().click({ timeout: 2000 });
    await page.waitForTimeout(1500);
    return true;
  } catch { return false; }
}

const browser = await chromium.launch({ headless: !process.env.HEADED, slowMo: process.env.HEADED ? 60 : 0 });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
await login(page);

const results = [];
let i = 0;
for (const wf of WFS) {
  i++;
  const rec = { slug: wf.slug, entity: wf.entity, trigger: wf.trigger, created: false, approved: false };
  try {
    await page.goto(BASE + `/e/${wf.entity}/new`, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    rec.created = await fillForm(page, i);
    const url = page.url();
    if (rec.created && wf.trigger === "record_updated") {
      const m = /status\s*=\s*"([^"]+)"/.exec(wf.cond || "");
      if (m) rec.approved = await setStatus(page, url, m[1].charAt(0).toUpperCase() + m[1].slice(1));
    }
  } catch (e) { rec.error = String(e).slice(0, 80); }
  log(`${wf.slug.padEnd(30)} entity=${wf.entity.padEnd(22)} created=${rec.created} ${wf.trigger === "record_updated" ? "approved=" + rec.approved : ""}`);
  results.push(rec);
}
fs.writeFileSync("E:/erp/_wf_sweep_result.json", JSON.stringify(results, null, 2));
log("=== triggered", results.filter((r) => r.created).length, "/", results.length, "workflow events ===");
await browser.close();
