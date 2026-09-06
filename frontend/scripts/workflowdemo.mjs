/**
 * Visible end-to-end workflow demo (School admission), with screenshots:
 *   owner creates an admission application → approves it → the enroll_on_approval
 *   workflow auto-creates the student → the teacher sees that student in their list.
 *
 *   node scripts/workflowdemo.mjs <slug> <ownerEmail> <ownerPw> <teacherEmail> <teacherPw>
 */
import { chromium } from "@playwright/test";

const [, , SLUG, OWNER, OWNER_PW, TEACHER, TEACHER_PW] = process.argv;
const BASE = "http://localhost:3000";
const OUT = "E:/erp/docs/screenshots/workflow";
const APPLICANT = "Diya Menon " + String(Date.now()).slice(-4); // unique so it's easy to spot
const log = (...a) => console.log("[wf]", ...a);

async function login(page, email, pw, slug) {
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', pw);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2500);
  await page.evaluate((s) => localStorage.setItem("nexus.ws", s), slug);
  await page.goto(BASE + "/home", { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
}
async function shot(page, name) {
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  log("shot", name);
}

const browser = await chromium.launch({ headless: !process.env.HEADED, slowMo: process.env.HEADED ? 140 : 0 });

// ---- OWNER: create + approve an admission application -----------------------
const owner = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const op = await owner.newPage();
await login(op, OWNER, OWNER_PW, SLUG);

await op.goto(BASE + "/e/admission_application", { waitUntil: "networkidle" });
await op.waitForTimeout(1500);
await shot(op, "01-owner-applications-list");

await op.goto(BASE + "/e/admission_application/new", { waitUntil: "networkidle" });
await op.waitForTimeout(1500);
// applicant_name is the first editable text field on the form — fill it directly
const applicantField = op.locator('form input[type="text"]:visible, form input:not([type]):visible').first();
await applicantField.fill(APPLICANT);
log("filled applicant_name =", APPLICANT);
// set gender if present (first option)
try {
  const g = op.locator('button[role="combobox"]').first();
  if (await g.count()) { await g.click(); await op.waitForTimeout(300); await op.locator('[role="option"]').first().click().catch(() => {}); await op.keyboard.press("Escape").catch(() => {}); }
} catch { /* noop */ }
await shot(op, "02-owner-new-application");
await op.locator('form button[type="submit"], button:has-text("Create")').first().click();
await op.waitForTimeout(2500);
const appUrl = op.url();
log("application created at", appUrl);
await shot(op, "03-owner-application-created");

// approve: open edit, set status = Approved, save
const editUrl = appUrl.endsWith("/edit") ? appUrl : appUrl.replace(/\/$/, "") + "/edit";
await op.goto(editUrl, { waitUntil: "networkidle" });
await op.waitForTimeout(1500);
try {
  // find the Status combobox and pick "Approved"
  const statusCombo = op.locator('button[role="combobox"][aria-label="Status"], button[role="combobox"]').last();
  await statusCombo.click();
  await op.waitForTimeout(400);
  await op.locator('[role="option"]:has-text("Approved")').first().click({ timeout: 3000 });
  await op.waitForTimeout(300);
  await shot(op, "04-owner-set-approved");
  await op.locator('form button[type="submit"], button:has-text("Save")').first().click();
  await op.waitForTimeout(3000);
  log("application approved");
} catch (e) {
  log("approve step issue", String(e).slice(0, 120));
}
await shot(op, "05-owner-after-approve");
// give the workflow time to run
await op.waitForTimeout(6000);
await owner.close();

// ---- TEACHER: sees the auto-created student --------------------------------
const teacher = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const tp = await teacher.newPage();
await login(tp, TEACHER, TEACHER_PW, SLUG);
await tp.goto(BASE + "/e/student", { waitUntil: "networkidle" });
await tp.waitForTimeout(2000);
// search for the applicant name if there's a search box
try {
  const search = tp.locator('input[placeholder*="Search"], input[type="search"]').first();
  if (await search.count()) { await search.fill(APPLICANT.split(" ")[0]); await tp.waitForTimeout(1500); }
} catch { /* noop */ }
await shot(tp, "06-teacher-sees-new-student");
log("APPLICANT was:", APPLICANT);
await teacher.close();
await browser.close();
log("done");
