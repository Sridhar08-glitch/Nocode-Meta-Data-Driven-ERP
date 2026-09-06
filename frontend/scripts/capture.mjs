/**
 * Browser-driven journey + data creation + screenshot capture for NexusERP.
 *
 * Everything is driven through the REAL frontend UI with Playwright (Chromium):
 * no ORM, no API seeding. Records are created by filling and submitting the
 * product's own metadata-driven forms — data flows through the real API,
 * validation, workflows and GL exactly as a user would trigger it.
 *
 * Modes:
 *   node scripts/capture.mjs auth       # unauthenticated auth pages only
 *   node scripts/capture.mjs journey    # register→verify→workspace→install; save session
 *   node scripts/capture.mjs data [N]   # create N records/entity via UI forms (default 50)
 *   node scripts/capture.mjs routes     # screenshot every app route (uses saved session)
 *   node scripts/capture.mjs showcase   # theme + view + chart UI/UX showcase shots
 *   node scripts/capture.mjs full [N]   # journey → data(N) → routes → showcase
 *
 * Env: BASE, API (backend), MAIL, BACKEND_LOG, OUT, STATE (storageState file)
 */
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const BASE = process.env.BASE || "http://localhost:3000";
const API = process.env.API || "http://localhost:8000";
const MAIL = process.env.MAIL || "E:/erp/_rc1_mail";
const BACKEND_LOG = process.env.BACKEND_LOG || "E:/erp/_run_backend.log";
const OUT = process.env.OUT || "E:/erp/docs/screenshots";
const STATE = process.env.STATE || "E:/erp/frontend/scripts/_state.json";
const JOURNEY = "E:/erp/frontend/scripts/_journey.json";
const VIEWPORT = { width: 1440, height: 900 };
const log = (...a) => console.log("[capture]", ...a);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}
function outPath(rel) {
  const p = path.join(OUT, rel);
  ensureDir(path.dirname(p));
  return p;
}
function readJourney() {
  try {
    return JSON.parse(fs.readFileSync(JOURNEY, "utf8"));
  } catch {
    return {};
  }
}

// ---------------------------------------------------------------- token read
function readToken(after) {
  const deadline = Date.now() + 12000;
  const grab = (text) => {
    const all = [...text.matchAll(/verify-email\?token=([A-Za-z0-9_\-]+)/g)];
    return all.length ? all[all.length - 1][1] : null;
  };
  while (Date.now() < deadline) {
    try {
      const files = fs
        .readdirSync(MAIL)
        .map((f) => path.join(MAIL, f))
        .filter((f) => fs.statSync(f).mtimeMs > after)
        .sort((a, b) => fs.statSync(a).mtimeMs - fs.statSync(b).mtimeMs);
      if (files.length) {
        const t = grab(fs.readFileSync(files[files.length - 1], "utf8"));
        if (t) return t;
      }
    } catch {
      /* noop */
    }
    try {
      const t = grab(fs.readFileSync(BACKEND_LOG, "utf8"));
      if (t) return t;
    } catch {
      /* noop */
    }
    const w = Date.now() + 300;
    while (Date.now() < w) {}
  }
  return null;
}

// ------------------------------------------------------------------ helpers
async function shot(page, rel, full = true) {
  try {
    await page.screenshot({ path: outPath(rel), fullPage: full });
    log("shot", rel);
  } catch (e) {
    log("shot FAILED", rel, String(e).slice(0, 100));
  }
}
async function goto(page, url) {
  try {
    await page.goto(BASE + url, { waitUntil: "networkidle", timeout: 30000 });
  } catch {
    try {
      await page.goto(BASE + url, { waitUntil: "domcontentloaded", timeout: 30000 });
    } catch (e) {
      log("goto FAILED", url, String(e).slice(0, 100));
    }
  }
  await page.waitForTimeout(700);
}

// realistic value generator keyed off a field's label/name/type
const FIRST = ["Ava", "Liam", "Noah", "Emma", "Olivia", "Sophia", "Mason", "Lucas", "Mia", "Amara", "Zara", "Omar", "Yusuf", "Priya", "Chen", "Diego", "Fatima", "Hana", "Ivan", "Nadia"];
const LAST = ["Carter", "Nguyen", "Patel", "Khan", "Silva", "Kim", "Lopez", "Haddad", "Rossi", "Okafor", "Weber", "Ahmed", "Cohen", "Mbeki", "Tanaka", "Novak"];
const COMPANY = ["Acme", "Globex", "Initech", "Umbrella", "Soylent", "Stark", "Wayne", "Hooli", "Vehement", "Massive Dynamic", "Cyberdyne", "Wonka", "Tyrell", "Aperture", "Gringotts", "Pied Piper"];
const CITY = ["Austin", "Denver", "Seattle", "Boston", "Dubai", "Berlin", "Lagos", "Mumbai", "Toronto", "Singapore"];
const WORDS = ["strategic", "quarterly", "priority", "renewal", "expansion", "onboarding", "follow-up", "discovery", "proposal", "enterprise"];
const pick = (a, i) => a[i % a.length];
const rand = (n) => Math.floor(Math.random() * n);

const COUNTRIES = ["United States", "India", "United Kingdom", "Canada", "Australia", "Germany", "Nigeria", "Brazil", "Japan", "Singapore"];
const BLOOD = ["O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-"];
const SUBJECTS = ["Mathematics", "English", "Science", "History", "Geography", "Physics", "Chemistry", "Biology", "Computer Science", "Art", "Music", "Physical Education"];
const RELIGION = ["Christianity", "Islam", "Hinduism", "Buddhism", "Judaism", "None"];
const PEOPLE_ENTITIES = /guardian|teacher|student|parent|contact|staff|employee|nurse|instructor|advisor|counsellor|person|member|donor|alumni/;

function valueFor(meta, i) {
  const label = (meta.label || meta.name || meta.placeholder || "").toLowerCase();
  const type = meta.type || "text";
  const entity = (meta.entity || "").toLowerCase();
  const person = `${pick(FIRST, i * 3 + rand(5))} ${pick(LAST, i * 2 + rand(7))}`;

  if (type === "number")
    return String(label.includes("year") ? 2020 + (i % 6) : label.match(/price|amount|cost|value|salary|revenue|budget|fee/) ? (i + 1) * 1250 + rand(500) : (i % 40) + 1);
  if (type === "date") return new Date(2024 + (i % 3), i % 12, (i % 27) + 1).toISOString().slice(0, 10);
  if (type === "email") return `${pick(FIRST, i).toLowerCase()}.${pick(LAST, i).toLowerCase()}${i}@example.com`;
  if (type === "tel" || label.match(/phone|mobile|tel|contact ?no/)) return `+1-555-${String(1000 + i).slice(-4)}`;
  if (type === "url" || label.match(/url|website|link/)) return `https://${pick(COMPANY, i).toLowerCase().replace(/\s/g, "")}.example.com`;
  if (label.match(/e-?mail/)) return `${pick(FIRST, i).toLowerCase()}${i}@example.com`;

  // people-ish specifics
  if (label.match(/first ?name/)) return pick(FIRST, i * 3 + rand(5));
  if (label.match(/last ?name|surname|family ?name/)) return pick(LAST, i * 2 + rand(7));
  if (label.match(/middle ?name/)) return pick(FIRST, i + 3);
  if (label.match(/blood/)) return pick(BLOOD, i);
  if (label.match(/nationality/)) return pick(COUNTRIES, i);
  if (label.match(/country/)) return pick(COUNTRIES, i);
  if (label.match(/religion/)) return pick(RELIGION, i);
  if (label.match(/city|town/)) return pick(CITY, i);
  if (label.match(/prior ?school|previous ?school|school ?name/)) return `${pick(CITY, i)} Public School`;
  if (label.match(/address|street/)) return `${100 + i} ${pick(LAST, i)} Ave, ${pick(CITY, i)}`;
  if (label.match(/occupation|profession|designation|job/)) return pick(["Engineer", "Doctor", "Teacher", "Accountant", "Manager", "Nurse", "Lawyer", "Consultant"], i);
  if (label.match(/qualification|degree/)) return pick(["B.Sc", "M.Sc", "B.Ed", "M.Ed", "Ph.D", "B.A", "M.A", "MBA"], i);
  if (label.match(/relationship/)) return pick(["Father", "Mother", "Guardian"], i);

  // codes / numbers
  if (label.match(/roll ?no|roll ?number/)) return String(1000 + i);
  if (label.match(/employee ?no|staff ?no|emp ?id/)) return `EMP-${1000 + i}`;
  if (label.match(/admission ?no/)) return `ADM-${2026}-${String(100 + i)}`;
  if (label.match(/code|sku|ref|reference|number|no\b/)) return `${(entity || "REC").slice(0, 3).toUpperCase()}-${1000 + i}`;

  // amounts
  if (label.match(/amount|price|cost|value|salary|revenue|budget|total|fee/)) return String((i + 1) * 1000 + rand(900));
  if (label.match(/qty|quantity|count|capacity|strength|marks|score|grade\b/)) return String((i % 40) + 1);

  // names / titles — entity-aware
  if (label.match(/full ?name|contact ?name|guardian ?name|parent ?name/)) return person;
  if (label === "name" || label.match(/^name$/)) {
    if (PEOPLE_ENTITIES.test(entity)) return person;
    if (entity.includes("subject")) return pick(SUBJECTS, i);
    if (entity.includes("class")) return `Grade ${(i % 12) + 1} - ${String.fromCharCode(65 + (i % 4))}`;
    if (entity.includes("house")) return pick(["Red House", "Blue House", "Green House", "Yellow House"], i);
    if (entity.includes("club")) return `${pick(["Science", "Art", "Debate", "Chess", "Drama", "Robotics"], i)} Club`;
    if (entity.includes("sport")) return pick(["Football", "Basketball", "Cricket", "Tennis", "Swimming", "Athletics"], i);
    if (entity.includes("subject")) return pick(SUBJECTS, i);
    if (entity.includes("term")) return `Term ${(i % 3) + 1}`;
    if (entity.includes("year")) return `${2024 + (i % 3)}-${2025 + (i % 3)}`;
    if (entity.includes("grade") || entity.includes("level")) return `Grade ${(i % 12) + 1}`;
    if (entity.includes("fee")) return `${pick(["Tuition", "Transport", "Library", "Lab", "Sports", "Exam"], i)} Fee`;
    if (entity.includes("book") || entity.includes("library")) return `${pick(["Introduction to", "Advanced", "Fundamentals of", "A Guide to"], i)} ${pick(SUBJECTS, i)}`;
    if (entity.includes("exam")) return `${pick(["Midterm", "Final", "Unit Test", "Quarterly"], i)} - ${pick(SUBJECTS, i)}`;
    return `${pick(SUBJECTS, i)} ${i + 1}`;
  }
  if (label.match(/title/)) return `${pick(["Introduction to", "Advanced", "Fundamentals of"], i)} ${pick(SUBJECTS, i)}`;
  if (label.match(/company|organi[sz]ation|vendor|supplier|customer|client/)) return `${pick(COMPANY, i)} ${pick(["Inc", "LLC", "Group", "Co", "Ltd"], i)}`;
  if (label.match(/description|note|comment|summary|detail|remark|reason/)) return `${pick(SUBJECTS, i)}-related note generated for the demo (#${i + 1}).`;
  return `${pick(SUBJECTS, i)} ${i + 1}`;
}

/**
 * Fill the visible create form and submit. Best-effort per control; returns true
 * if a submit was clicked. Handles native inputs/selects, textareas and Radix
 * comboboxes (button[role=combobox] → listbox option).
 */
async function fillAndSubmit(page, i, shotPath, entitySlug = "") {
  const form = page.locator("form").first();
  if (!(await form.count())) return false;

  // native inputs & textareas
  const controls = await form.locator("input:visible, textarea:visible, select:visible").all();
  for (const c of controls) {
    try {
      const tag = await c.evaluate((el) => el.tagName.toLowerCase());
      const type = (await c.getAttribute("type")) || "text";
      if (["hidden", "file", "submit", "button"].includes(type)) continue;
      if (type === "checkbox" || type === "radio") continue;
      const label = await c.evaluate((el) => {
        const id = el.getAttribute("id");
        let l = "";
        if (id) {
          const lab = document.querySelector(`label[for="${id}"]`);
          if (lab) l = lab.textContent || "";
        }
        return l || el.getAttribute("aria-label") || el.getAttribute("placeholder") || el.getAttribute("name") || "";
      });
      if (tag === "select") {
        const opts = await c.locator("option").all();
        for (let k = 1; k < opts.length; k++) {
          const v = await opts[k].getAttribute("value");
          if (v) {
            await c.selectOption(v).catch(() => {});
            break;
          }
        }
        continue;
      }
      const val = valueFor({ label, type, entity: entitySlug }, i);
      await c.fill(String(val)).catch(() => {});
    } catch {
      /* skip control */
    }
  }

  // Radix Select dropdowns (button[role=combobox] → portal listbox). Keyboard select
  // (ArrowDown + Enter) is the most reliable way to pick the first real option.
  const combos = await form.locator('button[role="combobox"]:visible').all();
  for (const cb of combos) {
    try {
      await cb.click({ timeout: 1500 });
      await page.waitForTimeout(400);
      const opt = page.locator('[role="option"]:visible').first();
      if (await opt.count()) await opt.click({ timeout: 1500 }).catch(() => {});
    } catch {
      /* ignore */
    }
    // ALWAYS close the dropdown — an open Radix Select overlay blocks the submit click.
    await page.keyboard.press("Escape").catch(() => {});
    await page.waitForTimeout(120);
  }

  // Relation lookups (Popover with a "Search…" trigger button listing existing records).
  // Only fillable when parent records already exist; pick the first available option.
  const lookups = await form.locator('button:has-text("Search…"), button:has-text("Search...")').all();
  for (const lk of lookups) {
    try {
      await lk.click({ timeout: 1500 });
      await page.waitForTimeout(600); // options load from the target entity
      // option rows are buttons inside the popover content (portal)
      const opt = page.locator('[data-radix-popper-content-wrapper] button, [role="dialog"] button').filter({ hasNotText: "Search" }).first();
      if (await opt.count()) await opt.click({ timeout: 1500 }).catch(() => {});
      await page.keyboard.press("Escape").catch(() => {});
      await page.waitForTimeout(150);
    } catch {
      await page.keyboard.press("Escape").catch(() => {});
    }
  }

  // Boolean switches/toggles — turn a portion on for realistic variety.
  if (i % 2 === 0) {
    const toggles = await form.locator('button[role="switch"]:visible').all();
    for (const tg of toggles) await tg.click({ timeout: 1000 }).catch(() => {});
  }

  // capture the completed form as the "form filling" example for this entity
  if (shotPath) await shot(page, shotPath, true);

  // submit
  const submit = form.locator('button[type="submit"], button:has-text("Save"), button:has-text("Create")').first();
  if (await submit.count()) {
    await submit.click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(700);
    return true;
  }
  return false;
}

// -------------------------------------------------------------------- modes
async function captureAuthPages(page) {
  log("=== auth pages ===");
  const pages = [
    ["/login", "auth/login.png"],
    ["/register", "auth/register.png"],
    ["/forgot-password", "auth/forgot-password.png"],
    ["/reset-password?token=demo-token", "auth/reset-password.png"],
    ["/verify-email", "auth/verify-email-error.png"],
  ];
  for (const [u, f] of pages) {
    await goto(page, u);
    await shot(page, f);
  }
}

async function journey(browser) {
  const ctx = await browser.newContext({ viewport: VIEWPORT });
  const page = await ctx.newPage();
  // discover entities from the app's own network calls
  const entitySet = new Map();
  page.on("response", async (res) => {
    try {
      const u = res.url();
      if (u.includes("/api/v1/metadata/entities/") && res.request().method() === "GET" && res.ok()) {
        const body = await res.json();
        const list = Array.isArray(body) ? body : body.results || [];
        for (const e of list) if (e && e.slug) entitySet.set(e.slug, { slug: e.slug, label: e.label || e.name || e.slug, can_create: e.can_create });
      }
    } catch {
      /* noop */
    }
  });

  await captureAuthPages(page);

  const ts = Date.now();
  const email = `owner${ts}@nexus.test`;
  const password = "OwnerStr0ng!pw2026";
  log("=== register owner ===", email);
  const t0 = Date.now();
  await goto(page, "/register");
  await page.fill("#full_name", "Olivia Owner");
  await page.fill("#email", email);
  await page.fill("#password", password);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(1500);

  const token = readToken(t0);
  if (!token) {
    log("!! no verification token — abort");
    await ctx.close();
    return null;
  }
  log("verify", token.slice(0, 10) + "...");
  await goto(page, `/verify-email?token=${token}`);
  await page.waitForTimeout(2500);

  let url = page.url();
  if (!url.includes("/workspaces/new")) await goto(page, "/workspaces/new");
  try {
    await page.fill("#ws-name", "Sridhar Demo");
    await page.click('button:has-text("Create workspace")');
    await page.waitForTimeout(2500);
    log("workspace created");
  } catch (e) {
    log("workspace step failed", String(e).slice(0, 100));
  }
  await shot(page, "workspace/onboarding-home.png");

  // install ALL packages through the real UI: each card → preview → consent → install
  await goto(page, "/solutions");
  await shot(page, "solutions/browse-authenticated.png");
  const cards = await page.locator('button[aria-label^="Preview "]').all();
  const names = [];
  for (const c of cards) {
    const l = await c.getAttribute("aria-label");
    if (l) names.push(l.replace(/^Preview /, ""));
  }
  log("packages to install:", names.join(", "));
  for (const name of names) {
    try {
      await goto(page, "/solutions");
      const card = page.locator(`button[aria-label="Preview ${name}"]`).first();
      await card.click({ timeout: 6000 });
      await page.waitForTimeout(1500);
      const consent = page.locator('input[aria-label="Consent to install"]');
      if (!(await consent.count())) {
        await page.keyboard.press("Escape").catch(() => {});
        log("  skip (already installed?):", name);
        continue;
      }
      await consent.check({ timeout: 4000 }).catch(() => consent.click({ timeout: 4000 }));
      const installBtn = page.locator('button:has-text("Install solution")');
      await installBtn.click({ timeout: 4000 });
      await page.locator('button:has-text("Install solution")').waitFor({ state: "detached", timeout: 60000 }).catch(() => {});
      await page.waitForTimeout(1500);
      log("  installed:", name);
    } catch (e) {
      log("  install failed:", name, String(e).slice(0, 100));
      await page.keyboard.press("Escape").catch(() => {});
    }
  }
  await goto(page, "/solutions");
  await shot(page, "solutions/installed-all.png");

  // trigger entity discovery: the app shell nav fetches /metadata/entities/
  await goto(page, "/home");
  await page.waitForTimeout(2000);
  await goto(page, "/crm");
  await page.waitForTimeout(2000);

  const slug = await page.evaluate(() => localStorage.getItem("nexus.ws"));
  const entities = [...entitySet.values()];
  fs.writeFileSync(JOURNEY, JSON.stringify({ email, password, slug, entities }, null, 2));
  await ctx.storageState({ path: STATE });
  log("journey saved — slug:", slug, "entities:", entities.map((e) => e.slug).join(", ") || "(none discovered)");
  await ctx.close();
  return { email, password, slug, entities };
}

// Authenticate ONCE via the API and inject the refresh token into localStorage so the
// app rehydrates the session without repeated UI logins (avoids the 5/min login throttle).
async function apiSession(page, email, password, slug) {
  const res = await fetch(API + "/api/v1/auth/login/", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!data.refresh) {
    log("apiSession FAILED:", JSON.stringify(data).slice(0, 120));
    return false;
  }
  await goto(page, "/login"); // land on the app origin to set localStorage
  await page.evaluate(({ r, s }) => {
    localStorage.setItem("nexus.refresh", r);
    if (s) localStorage.setItem("nexus.ws", s);
  }, { r: data.refresh, s: slug });
  await goto(page, "/home"); // app refreshes access from the injected refresh token
  await page.waitForTimeout(2500);
  return true;
}

// Log in fresh via the UI (robust against refresh-token rotation vs. stale storageState).
async function uiLogin(page, email, password, slug) {
  await goto(page, "/login");
  await page.fill('input[type="email"], #email', email).catch(() => {});
  await page.fill('input[type="password"], #password', password).catch(() => {});
  await page.click('button[type="submit"]').catch(() => {});
  await page.waitForTimeout(2500);
  if (slug) {
    await page.evaluate((s) => localStorage.setItem("nexus.ws", s), slug).catch(() => {});
    await page.reload({ waitUntil: "networkidle" }).catch(() => {});
    await page.waitForTimeout(1200);
  }
}

async function newSession(browser) {
  const j = readJourney();
  const ctx = await browser.newContext({ viewport: VIEWPORT });
  const page = await ctx.newPage();
  if (j.email && j.password) {
    await uiLogin(page, j.email, j.password, j.slug);
  } else {
    await goto(page, "/home");
  }
  await page.waitForTimeout(1000);
  return { ctx, page };
}

async function dataMode(browser, n) {
  const j = readJourney();
  let entities = j.entities || [];
  const { ctx, page } = await newSession(browser);
  // refresh entity discovery if empty
  if (!entities.length) {
    page.on("response", async (res) => {
      try {
        if (res.url().includes("/api/v1/metadata/entities/") && res.ok()) {
          const body = await res.json();
          const list = Array.isArray(body) ? body : body.results || [];
          entities = list.filter((e) => e.slug).map((e) => ({ slug: e.slug, label: e.label || e.slug, can_create: e.can_create }));
        }
      } catch {}
    });
    await goto(page, "/crm");
    await page.waitForTimeout(1500);
  }
  const targets = entities.filter((e) => e.can_create !== false);
  log(`=== data mode: ${targets.length} entities × ${n} records ===`);
  const summary = [];
  for (const e of targets) {
    let ok = 0;
    for (let i = 0; i < n; i++) {
      await goto(page, `/e/${e.slug}/new`);
      // one representative filled-form screenshot per entity (first record)
      const shotPath = i === 0 ? `records/${e.slug}-form-example.png` : undefined;
      const submitted = await fillAndSubmit(page, i, shotPath, e.slug);
      if (submitted) {
        // detect success: navigated away from /new or a toast/list appears
        await page.waitForTimeout(500);
        if (!page.url().includes("/new")) ok++;
      }
      if (i === 0 && !submitted) {
        log(`  ${e.slug}: form not fillable, skipping`);
        break;
      }
    }
    log(`  ${e.slug}: created ~${ok}/${n}`);
    summary.push({ slug: e.slug, created: ok });
    // capture populated list + views for this entity
    await goto(page, `/e/${e.slug}`);
    await shot(page, `records/${e.slug}-list.png`);
    await goto(page, `/e/${e.slug}/views`);
    await shot(page, `records/${e.slug}-views.png`);
  }
  fs.writeFileSync("E:/erp/frontend/scripts/_data_summary.json", JSON.stringify(summary, null, 2));
  await ctx.close();
  return summary;
}

const APP_ROUTES = [
  ["/home", "dashboard/home"], ["/search", "core/search"], ["/activity", "core/activity"],
  ["/solutions", "solutions/browse"], ["/solutions/new", "solutions/wizard-new"], ["/catalog", "solutions/process-catalog"],
  ["/crm", "crm/overview"], ["/accounting", "accounting/overview"], ["/accounting/accounts", "accounting/chart-of-accounts"],
  ["/accounting/journal", "accounting/journal"], ["/accounting/periods", "accounting/periods"], ["/accounting/reports", "accounting/reports"],
  ["/inventory", "inventory/overview"], ["/inventory/items", "inventory/items"], ["/inventory/stock", "inventory/stock"],
  ["/inventory/warehouses", "inventory/warehouses"], ["/inventory/movements", "inventory/movements"], ["/inventory/transactions", "inventory/transactions"],
  ["/procurement", "procurement/overview"], ["/hr", "hr/overview"], ["/payroll", "payroll/overview"], ["/payroll/runs", "payroll/runs"],
  ["/payroll/payslips", "payroll/payslips"], ["/payroll/structures", "payroll/structures"], ["/payroll/loans", "payroll/loans"],
  ["/assets", "assets/overview"], ["/assets/depreciation", "assets/depreciation"], ["/assets/disposals", "assets/disposals"],
  ["/projects", "projects/overview"], ["/projects/financials", "projects/financials"], ["/projects/schedule", "projects/schedule"], ["/projects/resources", "projects/resources"],
  ["/manufacturing", "manufacturing/overview"], ["/manufacturing/boms", "manufacturing/boms"], ["/manufacturing/orders", "manufacturing/orders"],
  ["/manufacturing/mrp", "manufacturing/mrp"], ["/manufacturing/quality", "manufacturing/quality"],
  ["/helpdesk", "helpdesk/overview"], ["/helpdesk/knowledge", "helpdesk/knowledge"], ["/helpdesk/sla", "helpdesk/sla"],
  ["/analytics", "analytics/scorecard"], ["/analytics/kpis", "analytics/kpis"], ["/analytics/scorecards", "analytics/scorecards"], ["/analytics/health", "analytics/health"],
  ["/reports", "reporting/reports"], ["/dashboards", "reporting/dashboards"], ["/query", "reporting/query-builder"],
  ["/approvals", "process/approvals"], ["/rules", "process/rules"], ["/sla", "process/sla"], ["/workflows", "process/workflows"], ["/calendars", "process/business-calendars"],
  ["/documents", "content/documents"], ["/templates", "content/notification-templates"], ["/templates/email", "content/email-templates"], ["/templates/documents", "content/document-templates"], ["/public-forms", "content/public-forms"],
  ["/import", "data/import"], ["/permissions", "admin/permissions"], ["/feature-flags", "admin/feature-flags"], ["/developer", "admin/developer-portal"],
  ["/studio", "studio/overview"], ["/studio/applications", "studio/applications"], ["/studio/home-layouts", "studio/home-layouts"], ["/studio/navigation", "studio/navigation"],
  ["/settings/security", "settings/security"], ["/settings/sessions", "settings/sessions"], ["/settings/notifications", "settings/notifications"],
  ["/admin", "admin/hub"], ["/admin/workspace", "admin/workspace"], ["/admin/members", "admin/members"], ["/admin/branding", "admin/branding"],
  ["/admin/localization", "admin/localization"], ["/admin/health", "admin/health"], ["/admin/audit", "admin/audit"], ["/admin/certification", "admin/certification"],
  ["/admin/config-vcs", "admin/config-vcs"], ["/admin/dependencies", "admin/dependencies"], ["/admin/lineage", "admin/lineage"], ["/admin/numbering", "admin/numbering"],
  ["/admin/marketplace", "admin/marketplace"], ["/admin/backups", "admin/backups"], ["/admin/recycle-bin", "admin/recycle-bin"], ["/admin/promotions", "admin/promotions"], ["/admin/portal", "admin/portal"],
];

async function routesMode(browser) {
  const { ctx, page } = await newSession(browser);
  log("=== routes (" + APP_ROUTES.length + ") ===");
  for (const [route, dest] of APP_ROUTES) {
    await goto(page, route);
    await shot(page, dest + ".png");
  }
  await ctx.close();
}

async function showcaseMode(browser) {
  const { ctx, page } = await newSession(browser);
  log("=== showcase: themes + views + charts ===");
  const j = readJourney();
  const firstEntity = (j.entities || []).find((e) => e.can_create !== false)?.slug || "lead";

  // theme: click the real toggle (button[aria-label="Toggle theme"]) for reliable next-themes flip
  await goto(page, "/home");
  await shot(page, "showcase/theme-light-home.png");
  const toggle = page.locator('button[aria-label="Toggle theme"]').first();
  try {
    await toggle.click({ timeout: 4000 });
    await page.waitForTimeout(900);
    await shot(page, "showcase/theme-dark-home.png");
    // also show a data-rich page in dark mode
    await goto(page, "/crm");
    await page.waitForTimeout(1000);
    await shot(page, "showcase/theme-dark-crm.png");
    await toggle.click({ timeout: 4000 }).catch(() => {}); // back to light
    await page.waitForTimeout(700);
  } catch (e) {
    log("theme toggle failed", String(e).slice(0, 100));
  }

  // view engine: /e/[entity]/views hosts a Select(aria-label="View type") with 10 kinds
  await goto(page, `/e/${firstEntity}/views`);
  await shot(page, "showcase/views-default.png");
  const kinds = ["Kanban", "Calendar", "Timeline", "Tree", "Org chart", "Map", "Pivot", "Gantt", "Chart", "Dashboard"];
  for (const label of kinds) {
    try {
      const trigger = page.locator('button[aria-label="View type"]').first();
      await trigger.click({ timeout: 3000 });
      await page.waitForTimeout(400);
      const opt = page.locator(`[role="option"]:has-text("${label}")`).first();
      await opt.click({ timeout: 3000 });
      await page.waitForTimeout(1400);
      await shot(page, `showcase/view-${label.toLowerCase().replace(/\s+/g, "-")}.png`);
    } catch {
      await page.keyboard.press("Escape").catch(() => {});
    }
  }

  // charts + dashboards
  await goto(page, "/dashboards");
  await shot(page, "showcase/dashboards.png");
  await goto(page, "/reports");
  await shot(page, "showcase/reports.png");
  await goto(page, "/analytics");
  await shot(page, "showcase/analytics-scorecard.png");

  // design-system component showcase route (dev)
  await goto(page, "/dev/components");
  await shot(page, "showcase/design-system-components.png");
  await ctx.close();
}

// Drive Admin → Branding to re-theme the whole app, then screenshot the result.
// This is the real mechanism that controls in-app look (colors/fonts/density/radius).
const BRAND_PRESETS = [
  {
    key: "indigo-default", label: "Indigo (default)",
    fields: { "b-app": "Sridhar ERP", "b-font-h": "Inter", "b-font-b": "Inter" },
    selects: { "b-density": "comfortable", "b-radius": "md" },
    colors: { Primary: "#6366f1", Secondary: "#8b5cf6", Accent: "#06b6d4", Background: "#ffffff", Surface: "#f8fafc", Text: "#0f172a" },
  },
  {
    key: "emerald", label: "Emerald / serif / compact",
    fields: { "b-app": "Sridhar ERP", "b-font-h": "Georgia, serif", "b-font-b": "Inter" },
    selects: { "b-density": "compact", "b-radius": "lg" },
    colors: { Primary: "#059669", Secondary: "#047857", Accent: "#10b981", Background: "#ffffff", Surface: "#ecfdf5", Text: "#052e16" },
  },
  {
    key: "midnight", label: "Midnight (dark) / rounded",
    fields: { "b-app": "Sridhar ERP", "b-font-h": "Poppins", "b-font-b": "Inter" },
    selects: { "b-density": "comfortable", "b-radius": "xl" },
    colors: { Primary: "#818cf8", Secondary: "#6366f1", Accent: "#22d3ee", Background: "#0b1220", Surface: "#111827", Text: "#e5e7eb" },
  },
  {
    key: "sunrise", label: "Sunrise / sharp corners",
    fields: { "b-app": "Sridhar ERP", "b-font-h": "Inter", "b-font-b": "Inter" },
    selects: { "b-density": "compact", "b-radius": "sm" },
    colors: { Primary: "#ea580c", Secondary: "#c2410c", Accent: "#f59e0b", Background: "#fffbeb", Surface: "#fff7ed", Text: "#431407" },
  },
];

async function brandingMode(browser) {
  const { ctx, page } = await newSession(browser);
  log("=== branding showcase: re-theming the app ===");
  await goto(page, "/admin/branding");
  await shot(page, "showcase/branding-admin.png");
  for (const preset of BRAND_PRESETS) {
    try {
      await goto(page, "/admin/branding");
      for (const [id, val] of Object.entries(preset.fields)) await page.fill(`#${id}`, val).catch(() => {});
      for (const [id, val] of Object.entries(preset.selects)) await page.selectOption(`#${id}`, val).catch(() => {});
      for (const [label, hex] of Object.entries(preset.colors)) await page.fill(`input[aria-label="${label} hex"]`, hex).catch(() => {});
      await page.click('button:has-text("Save branding")');
      await page.waitForTimeout(2000);
      // capture the re-themed shell on a couple of pages
      await goto(page, "/home");
      await shot(page, `showcase/brand-${preset.key}-home.png`);
      await goto(page, "/crm");
      await shot(page, `showcase/brand-${preset.key}-crm.png`);
      await goto(page, `/e/lead`);
      await shot(page, `showcase/brand-${preset.key}-list.png`);
      log("applied brand preset:", preset.key);
    } catch (e) {
      log("preset failed", preset.key, String(e).slice(0, 100));
    }
  }
  await ctx.close();
}

// Full per-package pipeline: own workspace → install ONE package → scoped-nav proof →
// discover entities → create N records/entity via UI → per-entity form + list screenshots.
async function packageMode(browser, pkgName, pkgSlug, n) {
  const j = readJourney();
  if (!j.email) {
    log("no owner creds in _journey.json — run journey first");
    return;
  }
  const ctx = await browser.newContext({ viewport: VIEWPORT });
  const page = await ctx.newPage();
  const entitySet = new Map();
  page.on("response", async (res) => {
    try {
      if (res.url().includes("/api/v1/metadata/entities/") && res.request().method() === "GET" && res.ok()) {
        const body = await res.json();
        const list = Array.isArray(body) ? body : body.results || [];
        for (const e of list) if (e && e.slug) entitySet.set(e.slug, { slug: e.slug, label: e.label || e.name || e.slug, can_create: e.can_create });
      }
    } catch {}
  });

  const dir = pkgSlug; // screenshots/<pkgSlug>/...
  await uiLogin(page, j.email, j.password); // no slug yet → new ws next
  // fresh workspace dedicated to this package
  await goto(page, "/workspaces/new");
  await page.fill("#ws-name", `Sridhar ${pkgName}`).catch(() => {});
  await page.click('button:has-text("Create workspace")').catch(() => {});
  await page.waitForTimeout(2500);
  const slug = await page.evaluate(() => localStorage.getItem("nexus.ws"));
  log(`[${pkgSlug}] workspace: ${slug}`);

  // install ONLY this package
  await goto(page, "/solutions");
  try {
    const card = page.locator(`button[aria-label="Preview ${pkgName}"]`).first();
    await card.click({ timeout: 6000 });
    await page.waitForTimeout(1500);
    const consent = page.locator('input[aria-label="Consent to install"]');
    await consent.check({ timeout: 4000 }).catch(() => consent.click({ timeout: 4000 }));
    await page.locator('button:has-text("Install solution")').click({ timeout: 4000 });
    await page.locator('button:has-text("Install solution")').waitFor({ state: "detached", timeout: 90000 }).catch(() => {});
    await page.waitForTimeout(2000);
    log(`[${pkgSlug}] installed`);
  } catch (e) {
    log(`[${pkgSlug}] install failed`, String(e).slice(0, 100));
  }

  // scoped-nav proof + overview (reload so installed-solutions gating applies;
  // wait for the installed-solutions query to settle before shooting).
  await goto(page, "/home");
  await page.reload({ waitUntil: "networkidle" }).catch(() => {});
  await page.waitForTimeout(4500);
  await shot(page, `${dir}/00-scoped-nav-home.png`);

  // discover THIS workspace's entities only: clear anything captured during login
  // (the owner's default workspace) and refetch inside the package workspace.
  entitySet.clear();
  await goto(page, "/home");
  await page.waitForTimeout(2500);
  await goto(page, "/query"); // another view that lists entities, to be safe
  await page.waitForTimeout(2000);
  const entities = [...entitySet.values()].filter((e) => e.can_create !== false);
  log(`[${pkgSlug}] entities: ${entities.length}`);

  const summary = [];
  for (const e of entities) {
    let ok = 0;
    for (let i = 0; i < n; i++) {
      await goto(page, `/e/${e.slug}/new`);
      const shotPath = i === 0 ? `${dir}/forms/${e.slug}-form.png` : undefined;
      const submitted = await fillAndSubmit(page, i, shotPath, e.slug);
      if (submitted) {
        await page.waitForTimeout(400);
        if (!page.url().includes("/new")) ok++;
      }
      if (i === 0 && !submitted) break;
    }
    await goto(page, `/e/${e.slug}`);
    await shot(page, `${dir}/lists/${e.slug}-list.png`);
    log(`[${pkgSlug}] ${e.slug}: ~${ok}/${n}`);
    summary.push({ slug: e.slug, created: ok });
  }
  fs.writeFileSync(`E:/erp/frontend/scripts/_pkg_${pkgSlug}.json`, JSON.stringify({ slug, pkgSlug, summary }, null, 2));
  log(`[${pkgSlug}] DONE — ${summary.length} entities`);
  await ctx.close();
}

// A SIMPLE, presentable School demo for a GitHub showcase: a clean workspace with
// the key entities populated in dependency order (masters first → lookups resolve),
// modest volume, clean screenshots. Not the exhaustive 50/entity grind.
const SIMPLE_SCHOOL = [
  ["academic_year", 3], ["term", 4], ["grade_level", 6], ["subject", 10],
  ["teacher", 12], ["school_class", 8], ["guardian", 15], ["student", 20],
  ["fee_category", 6], ["fee_structure", 6], ["exam", 6], ["club", 6],
  ["house", 4], ["library_book", 12], ["sport", 6],
];

async function simpleSchoolMode(browser) {
  const j = readJourney();
  const ctx = await browser.newContext({ viewport: VIEWPORT });
  const page = await ctx.newPage();
  const dir = "school";
  await uiLogin(page, j.email, j.password);
  await goto(page, "/workspaces/new");
  await page.fill("#ws-name", "Sridhar School").catch(() => {});
  await page.click('button:has-text("Create workspace")').catch(() => {});
  await page.waitForTimeout(2500);
  const slug = await page.evaluate(() => localStorage.getItem("nexus.ws"));
  log(`[simple-school] workspace: ${slug}`);

  await goto(page, "/solutions");
  try {
    await page.locator('button[aria-label="Preview School Management"]').first().click({ timeout: 6000 });
    await page.waitForTimeout(1500);
    const consent = page.locator('input[aria-label="Consent to install"]');
    await consent.check({ timeout: 4000 }).catch(() => consent.click({ timeout: 4000 }));
    await page.locator('button:has-text("Install solution")').click({ timeout: 4000 });
    await page.locator('button:has-text("Install solution")').waitFor({ state: "detached", timeout: 90000 }).catch(() => {});
    await page.waitForTimeout(2000);
    log("[simple-school] installed");
  } catch (e) {
    log("[simple-school] install failed", String(e).slice(0, 100));
  }

  await goto(page, "/home");
  await page.reload({ waitUntil: "networkidle" }).catch(() => {});
  await page.waitForTimeout(4500);
  await shot(page, `${dir}/00-scoped-nav.png`);

  const summary = [];
  for (const [slugE, count] of SIMPLE_SCHOOL) {
    let ok = 0;
    for (let i = 0; i < count; i++) {
      await goto(page, `/e/${slugE}/new`);
      const shotPath = i === 0 ? `${dir}/forms/${slugE}-form.png` : undefined;
      const submitted = await fillAndSubmit(page, i, shotPath, slugE);
      if (submitted) {
        await page.waitForTimeout(400);
        if (!page.url().includes("/new")) ok++;
      }
      if (i === 0 && !submitted) break;
    }
    await goto(page, `/e/${slugE}`);
    await shot(page, `${dir}/lists/${slugE}-list.png`);
    log(`[simple-school] ${slugE}: ~${ok}/${count}`);
    summary.push({ slug: slugE, created: ok });
  }
  // a couple of overview shots for the README
  await goto(page, "/dashboards");
  await shot(page, `${dir}/dashboards.png`);
  await goto(page, "/reports");
  await shot(page, `${dir}/reports.png`);
  fs.writeFileSync("E:/erp/frontend/scripts/_simple_school.json", JSON.stringify({ slug, summary }, null, 2));
  log(`[simple-school] DONE — ${summary.length} entities`);
  await ctx.close();
}

// Capture list + filled-form screenshots for EVERY entity (logged in as owner).
async function allEntitiesMode(browser) {
  const slugs = JSON.parse(fs.readFileSync("E:/erp/_entities.json", "utf8"));
  const email = process.argv[3], pw = process.argv[4], slug = process.argv[5];
  const ctx = await browser.newContext({ viewport: VIEWPORT });
  const page = await ctx.newPage();
  await uiLogin(page, email, pw, slug);
  // confirm we're authenticated (not bounced to /login) before capturing
  if (page.url().includes("/login")) { log("login failed — aborting"); await ctx.close(); return; }
  log(`=== all entities: ${slugs.length} (list + form) ===`);
  let i = 0;
  for (const s of slugs) {
    i++;
    await goto(page, `/e/${s}`);
    await shot(page, `entities/${s}/01-list.png`);
    await goto(page, `/e/${s}/new`);
    await page.waitForTimeout(600);
    await fillAndSubmit(page, i + 3, `entities/${s}/02-form.png`, s);
    log(`  [${i}/${slugs.length}] ${s}`);
  }
  await ctx.close();
}

async function main() {
  const mode = process.argv[2] || "full";
  const n = parseInt(process.argv[3] || "50", 10);
  const headed = !!process.env.HEADED;
  const browser = await chromium.launch({ headless: !headed, slowMo: headed ? 120 : 0 });
  try {
    if (mode === "auth") {
      const ctx = await browser.newContext({ viewport: VIEWPORT });
      const page = await ctx.newPage();
      await captureAuthPages(page);
      await ctx.close();
    } else if (mode === "journey") {
      await journey(browser);
    } else if (mode === "data") {
      await dataMode(browser, n);
    } else if (mode === "routes") {
      await routesMode(browser);
    } else if (mode === "showcase") {
      await showcaseMode(browser);
    } else if (mode === "branding") {
      await brandingMode(browser);
    } else if (mode === "simpleschool") {
      await simpleSchoolMode(browser);
    } else if (mode === "fillcheck") {
      // node capture.mjs fillcheck <slug> <entity>  → fill one create form, screenshot it
      const j = readJourney();
      const ctx = await browser.newContext({ viewport: VIEWPORT });
      const page = await ctx.newPage();
      await uiLogin(page, j.email, j.password, process.argv[3]);
      await goto(page, `/e/${process.argv[4]}/new`);
      await page.waitForTimeout(1500);
      await fillAndSubmit(page, 0, `_verify/fillcheck-${process.argv[4]}.png`, process.argv[4]);
      await ctx.close();
    } else if (mode === "allentities") {
      await allEntitiesMode(browser);
    } else if (mode === "package") {
      // node capture.mjs package "School Management" school 50
      await packageMode(browser, process.argv[3], process.argv[4], parseInt(process.argv[5] || "50", 10));
    } else {
      const j = await journey(browser);
      if (j) {
        await dataMode(browser, n);
        await routesMode(browser);
        await showcaseMode(browser);
      }
    }
  } finally {
    await browser.close();
  }
  log("=== capture complete:", mode, "===");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
