"""Set up one workspace member per role (invite → set password → assign custom role).

Uses the REAL REST API (owner-authorized) — the same flows the UI drives. Reads each
invitee's set-password token from the backend run log (console email sink).

Usage: python _setup_role_users.py <workspace_slug> <owner_email> <owner_password>
Prints JSON creds for each role user.
"""
import json
import re
import sys
import time

import requests

BASE = "http://localhost:8000"
LOG = r"E:/erp/_run_backend.log"
SLUG, OWNER_EMAIL, OWNER_PW = sys.argv[1], sys.argv[2], sys.argv[3]

# every School role -> demo email (slug@sridhar.test)
ROLE_SLUGS = [
    "school_administrator", "principal", "vice_principal", "transport_manager",
    "hostel_manager", "auditor", "registrar", "teacher", "academic_coordinator",
    "accountant", "finance_manager", "librarian", "class_teacher", "counsellor",
    "school_nurse", "medical_officer", "sports_coordinator", "club_coordinator",
]
ROLES = {s: f"{s}@sridhar.test" for s in ROLE_SLUGS}
PW = "R0leUserStr0ng!pw"


def owner_token():
    r = requests.post(f"{BASE}/api/v1/auth/login/", json={"email": OWNER_EMAIL, "password": OWNER_PW}, timeout=30)
    return r.json()["access"]


def token_for_email(email, after):
    """Newest set-password token addressed to `email` in the backend console log."""
    deadline = time.time() + 8
    while time.time() < deadline:
        try:
            text = open(LOG, encoding="utf-8", errors="replace").read()
        except OSError:
            text = ""
        # split into email blocks; find the block addressed To: email with a reset token
        blocks = re.split(r"\n(?=Content-Type:|MIME-Version:|To:)", text)
        hits = [b for b in blocks if f"To: {email}" in b and "reset-password?token=" in b]
        if hits:
            m = re.search(r"reset-password\?token=([A-Za-z0-9_\-]+)", hits[-1])
            if m:
                return m.group(1)
        time.sleep(0.4)
    return None


def main():
    access = owner_token()
    H = {"Authorization": f"Bearer {access}", "X-Workspace-Slug": SLUG, "Content-Type": "application/json"}
    # lift the Free-plan member cap so all 18 roles can be created
    up = requests.patch(f"{BASE}/api/v1/workspaces/{SLUG}/", headers=H, json={"plan": "enterprise"}, timeout=30)
    print(f"  plan -> {up.json().get('plan', up.status_code)}", file=sys.stderr)
    # role slug -> role id
    r = requests.get(f"{BASE}/api/v1/permissions/roles/", headers=H, timeout=30).json()
    roles = r if isinstance(r, list) else r.get("results", [])
    role_id = {x["slug"]: x["id"] for x in roles}

    out = []
    for slug, email in ROLES.items():
        rid = role_id.get(slug)
        if not rid:
            print(f"  ! role '{slug}' not found", file=sys.stderr)
            continue
        t0 = time.time()
        inv = requests.post(f"{BASE}/api/v1/workspaces/{SLUG}/members/",
                            headers=H, json={"email": email, "full_name": slug.replace("_", " ").title(), "role": "member"}, timeout=30)
        if inv.status_code not in (200, 201):
            print(f"  ! invite {email}: {inv.status_code} {inv.text[:100]}", file=sys.stderr)
            continue
        mid = inv.json()["id"]
        tok = token_for_email(email, t0)
        if tok:
            requests.post(f"{BASE}/api/v1/auth/password-reset/confirm/", json={"token": tok, "password": PW}, timeout=30)
        # assign the custom role
        requests.patch(f"{BASE}/api/v1/workspaces/{SLUG}/members/{mid}/", headers=H, json={"custom_role_id": rid}, timeout=30)
        out.append({"role": slug, "email": email, "password": PW})
        print(f"  set up {slug:16s} -> {email}", file=sys.stderr)

    print(json.dumps(out))


if __name__ == "__main__":
    main()
