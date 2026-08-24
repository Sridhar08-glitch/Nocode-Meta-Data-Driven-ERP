"""NexusERP Enterprise Acceptance Simulation harness.

Drives the REAL product over its REST API (same auth/permissions/RLS/validation
the frontend uses). No ORM, no direct SQL, no Redis manipulation. Email tokens
are read from the file email sink (the customer's inbox). Every operation is
recorded with verification so the deliverable reports are built from real
runtime evidence.

Run stages:  python eat.py p1   |  p234  |  days [N]  |  reports
State persists in sim/state/eat_state.json so stages chain without recreating
master data (continuity across the 50 business days).
"""
import glob
import json
import os
import re
import sys
import time

import requests

BASE = "http://127.0.0.1:8077"
MAIL = r"E:\erp\_rc1_mail"
STATE_DIR = os.path.join(os.path.dirname(__file__), "state")
STATE_FILE = os.path.join(STATE_DIR, "eat_state.json")
LOG_FILE = os.path.join(STATE_DIR, "eat_oplog.jsonl")
os.makedirs(STATE_DIR, exist_ok=True)

PW = "Sim3rStr0ng!pw2026"


# --------------------------------------------------------------------------- #
# state + recorder
# --------------------------------------------------------------------------- #
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"ids": {}, "stats": {}, "gaps": [], "capabilities": {}}


def save_state(st):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2, default=str)


class Recorder:
    def __init__(self, state):
        self.s = state
        self.s.setdefault("stats", {})
        self.s.setdefault("capabilities", {})
        self.s.setdefault("gaps", [])
        self.ops = 0
        self.ok = 0
        self.fail = 0

    def op(self, module, action, ok, status_code=None, detail="", day=None):
        self.ops += 1
        if ok:
            self.ok += 1
        else:
            self.fail += 1
        st = self.s["stats"].setdefault(module, {"ok": 0, "fail": 0})
        st["ok" if ok else "fail"] += 1
        rec = {"t": int(time.time()), "day": day, "module": module, "action": action,
               "ok": ok, "status": status_code, "detail": detail[:300]}
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        flag = "OK " if ok else "ERR"
        line = f"  [{flag}] {module}.{action} ({status_code})"
        if not ok:
            line += f" -- {detail[:200]}"
        print(line)
        return ok

    def capability(self, name, status, evidence="", impact="", priority="", phase=""):
        # status: COMPLETE | PARTIAL | NOT_IMPLEMENTED
        self.s["capabilities"][name] = {"status": status, "evidence": evidence[:300]}
        if status == "NOT_IMPLEMENTED":
            self.s["gaps"].append({"capability": name, "evidence": evidence[:300],
                                   "impact": impact, "priority": priority, "phase": phase})
        print(f"  CAP[{status}] {name}" + (f" -- {evidence[:120]}" if evidence else ""))


# --------------------------------------------------------------------------- #
# http client
# --------------------------------------------------------------------------- #
class Client:
    def __init__(self, access=None, slug=None):
        self.s = requests.Session()
        self.access = access
        self.slug = slug

    def h(self, extra=None):
        d = {"Content-Type": "application/json"}
        if self.access:
            d["Authorization"] = f"Bearer {self.access}"
        if self.slug:
            d["X-Workspace-Slug"] = self.slug
        if extra:
            d.update(extra)
        return d

    def get(self, p, **kw):
        return self.s.get(BASE + p, headers=self.h(), timeout=120, **kw)

    def post(self, p, payload=None, **kw):
        return self.s.post(BASE + p, data=json.dumps(payload or {}), headers=self.h(), timeout=120, **kw)

    def patch(self, p, payload=None, **kw):
        return self.s.patch(BASE + p, data=json.dumps(payload or {}), headers=self.h(), timeout=120, **kw)

    def delete(self, p, **kw):
        return self.s.delete(BASE + p, headers=self.h(), timeout=120, **kw)


def jlist(r):
    """Normalise list responses (bare array or {results})."""
    try:
        d = r.json()
    except Exception:
        return []
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        return d.get("results", [])
    return []


def token_after(ts):
    end = time.time() + 12
    while time.time() < end:
        fresh = [f for f in glob.glob(os.path.join(MAIL, "*")) if os.path.getmtime(f) > ts]
        if fresh:
            fresh.sort(key=os.path.getmtime)
            body = open(fresh[-1], encoding="utf-8", errors="replace").read()
            m = re.search(r"token=([A-Za-z0-9_\-]+)", body)
            if m:
                return m.group(1)
        time.sleep(0.3)
    return None


# --------------------------------------------------------------------------- #
# PHASE 1 — customer journey: register -> verify -> login -> workspace -> install
# --------------------------------------------------------------------------- #
ALL_SOLUTIONS = ["crm", "procurement", "hr", "assets", "projects", "helpdesk", "analytics"]
NATIVE_SETUPS = [  # native engines expose /setup/
    ("crm", "/api/v1/crm/setup/"),
    ("procurement", "/api/v1/procurement/setup/"),
    ("hr", "/api/v1/hr/setup/"),
    ("assets", "/api/v1/assets/setup/"),
    ("projects", "/api/v1/projects/setup/"),
    ("helpdesk", "/api/v1/helpdesk/setup/"),
    ("analytics", "/api/v1/analytics/setup/"),
    ("manufacturing", "/api/v1/manufacturing/setup/"),
    ("payroll", "/api/v1/payroll/setup/"),
]


def phase1(st, rec):
    anon = Client()
    email = st["ids"].get("owner_email") or f"founder@nexus-eat.test"
    st["ids"]["owner_email"] = email

    t0 = time.time()
    r = anon.post("/api/v1/auth/register/", {"email": email, "password": PW, "full_name": "EAT Founder"})
    if r.status_code == 400 and "exist" in r.text.lower():
        rec.op("onboard", "register(exists)", True, r.status_code)
    else:
        rec.op("onboard", "register", r.status_code == 201, r.status_code, r.text)
        tok = token_after(t0)
        rec.op("onboard", "verify_email", bool(tok) and anon.post("/api/v1/auth/verify-email/", {"token": tok}).status_code == 200, 200 if tok else 0)

    r = anon.post("/api/v1/auth/login/", {"email": email, "password": PW})
    rec.op("onboard", "login", r.status_code == 200, r.status_code, r.text)
    access = r.json().get("access")
    owner = Client(access)

    # workspace (reuse if present)
    wss = jlist(owner.get("/api/v1/workspaces/")) or owner.get("/api/v1/workspaces/").json()
    if isinstance(wss, list) and wss:
        slug = wss[0]["slug"]
        rec.op("onboard", "workspace(reuse)", True, 200, slug)
    else:
        r = owner.post("/api/v1/workspaces/", {"name": "Helios Manufacturing Group"})
        rec.op("onboard", "create_workspace", r.status_code == 201, r.status_code, r.text)
        slug = r.json().get("slug")
    st["ids"]["slug"] = slug
    owner.slug = slug
    st["ids"]["owner_access"] = access

    # configure workspace
    r = owner.patch(f"/api/v1/workspaces/{slug}/", {"plan": "enterprise"})
    rec.op("onboard", "configure_workspace", r.status_code == 200, r.status_code, r.text)

    # branding (logo/profile/timezone/currency) — probe capability
    r = owner.get("/api/v1/branding/")
    rec.capability("Branding/company profile", "COMPLETE" if r.status_code == 200 else "PARTIAL", f"GET /branding/ {r.status_code}")
    r = owner.get("/api/v1/localization/locale/")
    rec.capability("Localization (timezone/currency)", "COMPLETE" if r.status_code == 200 else "PARTIAL", f"GET /localization/locale/ {r.status_code}")

    # install all solution templates
    tpls = jlist(owner.get("/api/v1/solution-templates/"))
    by_slug = {t.get("slug"): t for t in tpls}
    installed = {i.get("solution_slug") for i in jlist(owner.get("/api/v1/solution-templates/installed/"))}
    for s in ALL_SOLUTIONS:
        if s in installed:
            rec.op("install", f"{s}(already)", True, 200)
            continue
        tpl = by_slug.get(s)
        if not tpl:
            rec.op("install", f"{s}(no-template)", False, 404)
            continue
        r = owner.post(f"/api/v1/solution-templates/{tpl['id']}/install/", {})
        rec.op("install", f"solution:{s}", r.status_code in (200, 201), r.status_code, r.text)

    # native setups (numbering sequences, native roles/nav)
    for name, path in NATIVE_SETUPS:
        r = owner.post(path, {})
        rec.op("install", f"setup:{name}", r.status_code in (200, 201), r.status_code, r.text[:200])

    # verify installation
    inst = jlist(owner.get("/api/v1/solution-templates/installed/"))
    rec.op("install", "verify_installed", len(inst) >= len(ALL_SOLUTIONS), 200, f"installed={len(inst)}")
    ents = jlist(owner.get("/api/v1/metadata/entities/"))
    rec.op("install", "verify_entities", len(ents) >= 30, 200, f"entities={len(ents)}")
    st["ids"]["entity_count"] = len(ents)
    accts = jlist(owner.get("/api/v1/ledger/accounts/"))
    rec.op("install", "verify_chart_of_accounts", len(accts) >= 10, 200, f"accounts={len(accts)}")

    save_state(st)
    return owner


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "p1"
    state = load_state()
    rec = Recorder(state)
    if stage == "p1":
        print("===== PHASE 1: CUSTOMER JOURNEY + INSTALL =====")
        phase1(state, rec)
    save_state(state)
    print(f"\n[{stage}] ops={rec.ops} ok={rec.ok} fail={rec.fail}")
