import { chromium } from "@playwright/test";
import fs from "node:fs";

const j = JSON.parse(fs.readFileSync("E:/erp/frontend/scripts/_journey.json", "utf8"));
const slug = process.argv[2] || "sridhar-school-management";
const BASE = "http://localhost:3000";

const b = await chromium.launch({ headless: true });
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();
await p.goto(BASE + "/login", { waitUntil: "networkidle" });
await p.fill('input[type="email"]', j.email);
await p.fill('input[type="password"]', j.password);
await p.click('button[type="submit"]');
await p.waitForTimeout(2500);
await p.evaluate((s) => localStorage.setItem("nexus.ws", s), slug);
await p.goto(BASE + "/home", { waitUntil: "networkidle" });
await p.waitForTimeout(4000); // let installed-solutions query settle
// dump the visible sidebar link labels
const labels = await p.$$eval('nav[aria-label="Primary"] a', (as) => as.map((a) => a.textContent.trim()));
console.log("WORKSPACE:", slug);
console.log("SIDEBAR LINKS:", JSON.stringify(labels));
await p.screenshot({ path: `E:/erp/docs/screenshots/_verify/nav-${slug}.png`, fullPage: true });
console.log("shot: _verify/nav-" + slug + ".png");
await b.close();
