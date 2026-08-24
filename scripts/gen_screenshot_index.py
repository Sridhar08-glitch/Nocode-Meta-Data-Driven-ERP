"""Generate docs/SCREENSHOT_INDEX.md from the captured PNGs.

Reproducible: re-run after any capture pass to refresh the index.
"""
import os
from datetime import date

ROOT = r"E:\erp\docs\screenshots"
OUT = r"E:\erp\docs\SCREENSHOT_INDEX.md"

GROUP_TITLES = {
    "auth": "Authentication",
    "workspace": "Workspace onboarding",
    "solutions": "Solution templates",
    "records": "Records runtime (data created in-browser)",
    "showcase": "UI / UX showcase (themes, views, branding)",
    "dashboard": "Dashboard / Home",
    "core": "Core (search, activity)",
    "crm": "CRM",
    "accounting": "Accounting",
    "inventory": "Inventory",
    "procurement": "Procurement",
    "hr": "HR",
    "payroll": "Payroll",
    "assets": "Assets",
    "projects": "Projects & PSA",
    "manufacturing": "Manufacturing",
    "helpdesk": "Helpdesk / ITSM",
    "analytics": "Analytics & KPI",
    "reporting": "Reporting",
    "process": "Process (approvals, rules, SLA, workflows)",
    "content": "Content (documents, templates, forms)",
    "data": "Data import/export",
    "studio": "Studio (app builder)",
    "settings": "User settings",
    "admin": "Administration",
}


def title_for(top):
    return GROUP_TITLES.get(top, top.replace("-", " ").title())


def humanize(name):
    return name.replace(".png", "").replace("-", " ").replace("_", " ").strip().title()


def main():
    groups = {}
    for dirpath, _dirs, files in os.walk(ROOT):
        for f in sorted(files):
            if not f.lower().endswith(".png"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, f), ROOT).replace("\\", "/")
            top = rel.split("/")[0]
            groups.setdefault(top, []).append(rel)

    total = sum(len(v) for v in groups.values())
    lines = []
    lines.append("# Sridhar ERP — Screenshot Index")
    lines.append("")
    lines.append(f"> Auto-generated from `docs/screenshots/` by `scripts/gen_screenshot_index.py`.")
    lines.append(f"> {total} screenshots across {len(groups)} sections. Last generated: {date.today().isoformat()}.")
    lines.append("")
    lines.append("All screenshots were captured by driving the **real product UI** with Playwright "
                 "(register → verify → workspace → install → create records → screenshot). "
                 "Record data was created through the app's own forms, not seeded via code.")
    lines.append("")
    for top in sorted(groups, key=lambda t: title_for(t).lower()):
        lines.append(f"## {title_for(top)}")
        lines.append("")
        lines.append("| Screenshot | File |")
        lines.append("|---|---|")
        for rel in groups[top]:
            name = humanize(rel.split("/")[-1])
            lines.append(f"| {name} | [`{rel}`](screenshots/{rel}) |")
        lines.append("")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"wrote {OUT} — {total} screenshots, {len(groups)} sections")


if __name__ == "__main__":
    main()
