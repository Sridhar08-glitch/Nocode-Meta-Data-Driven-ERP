"""Seed a realistic INDIAN SCHOOL into the School package — every field populated.

Structure (as requested): Classes 1-12, 10 different students each (120 students),
Indian names/context, with the supporting master data (academic year, terms, grade
levels, subjects, teachers, guardians) so all lookups resolve. Records go through the
real RecordService.create_record path (auto-numbers, rules, RLS apply). Every promoted,
non server-managed field gets a value — no empty columns.

Usage:  python _seed_school.py <workspace_slug>
"""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.sandbox")
import django  # noqa: E402

django.setup()

from apps.accounts.models import User  # noqa: E402
from apps.metadata.models import EntityDefinition, FieldDefinition  # noqa: E402
from apps.records.services import RecordService  # noqa: E402
from apps.tenancy.models import Workspace, WorkspaceMember  # noqa: E402
from apps.tenancy.rls import workspace_context  # noqa: E402

SLUG = sys.argv[1] if len(sys.argv) > 1 else "sridhar-school-4"

FIRST_M = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna",
           "Ishaan", "Rohan", "Kabir", "Ansh", "Dhruv", "Advik", "Rudra", "Yuvan", "Om", "Atharv", "Veer"]
FIRST_F = ["Ananya", "Diya", "Aadhya", "Saanvi", "Pari", "Anaya", "Aarohi", "Ira", "Myra", "Riya",
           "Priya", "Kavya", "Ishani", "Navya", "Sara", "Anvi", "Kiara", "Prisha", "Siya", "Tara"]
LAST = ["Sharma", "Verma", "Gupta", "Patel", "Reddy", "Nair", "Iyer", "Rao", "Singh", "Kumar",
        "Menon", "Pillai", "Desai", "Joshi", "Mehta", "Shah", "Bose", "Das", "Chauhan", "Malhotra"]
CITY = ["Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata", "Hyderabad", "Pune", "Ahmedabad", "Jaipur", "Lucknow"]
SUBJECTS = ["English", "Hindi", "Mathematics", "Science", "Social Studies", "Sanskrit",
            "Computer Science", "Environmental Studies", "Physical Education", "Art & Craft"]
BLOOD = ["O+", "A+", "B+", "AB+", "O-", "A-", "B-"]
n = {"i": 0}


def person(i, female=None):
    female = (i % 2 == 0) if female is None else female
    fn = (FIRST_F if female else FIRST_M)[i % 20]
    return fn, LAST[(i * 3) % len(LAST)], ("female" if female else "male")


def generic_value(fd, entity_slug, i, registry):
    """Fill any field with sensible Indian data; resolve lookups from the registry."""
    ft, cfg = fd.field_type, (fd.config or {})
    label, slug = (fd.name or fd.slug).lower(), fd.slug.lower()
    if ft in ("auto_number", "formula", "rollup"):
        return None
    if ft in ("select", "status", "multi_select"):
        ch = cfg.get("choices") or cfg.get("options") or []
        if not ch:
            return None
        v = ch[i % len(ch)]
        return [v] if ft == "multi_select" else v
    if ft == "boolean":
        return i % 3 != 0
    if ft in ("date",):
        return f"{2015 + (i % 11)}-{(i % 12) + 1:02d}-{(i % 27) + 1:02d}"
    if ft in ("datetime", "time"):  # some 'time' fields map to timestamptz — use a full timestamp
        return f"{2015 + (i % 11)}-{(i % 12) + 1:02d}-{(i % 27) + 1:02d}T{8 + (i % 8):02d}:{(i % 6) * 10:02d}:00"
    if ft in ("lookup", "relation", "user", "multirelation", "multiuser"):
        t = cfg.get("target_entity_slug") or cfg.get("target_entity")
        ids = registry.get(t, [])
        if not ids:
            return None
        v = ids[i % len(ids)]
        return [v] if ft in ("multirelation", "multiuser") else v
    if ft in ("integer", "number", "decimal", "currency", "percentage", "rating", "duration", "progress"):
        if "year" in label:
            return 2024 + (i % 3)
        if any(k in label for k in ("fee", "amount", "price", "cost", "salary")):
            return (i % 20 + 1) * 2500
        if any(k in label for k in ("mark", "score", "percent", "grade")):
            return 55 + (i % 45)
        if "capacity" in label or "strength" in label:
            return 40
        return (i % 30) + 1
    if ft == "email":
        return f"user{i}@indianschool.edu.in"
    if ft in ("phone", "tel"):
        return f"+91-9{i % 10}{(i * 7) % 100000000:08d}"
    if ft == "url":
        return "https://indianschool.edu.in"
    # text
    fn, ln, _ = person(i)
    if "email" in label:
        return f"{fn.lower()}.{ln.lower()}{i}@indianschool.edu.in"
    if any(k in label for k in ("phone", "mobile", "contact no", "guardian_phone")):
        return f"+91-9{i % 10}{(i * 7) % 100000000:08d}"
    if "blood" in label:
        return BLOOD[i % len(BLOOD)]
    if "nationality" in label or "country" in label:
        return "India"
    if "city" in label:
        return CITY[i % len(CITY)]
    if "address" in label:
        return f"{i + 1}, MG Road, {CITY[i % len(CITY)]}"
    if "first" in label and "name" in label:
        return fn
    if ("last" in label and "name" in label) or "surname" in label:
        return ln
    if "subject" in label:
        return SUBJECTS[i % len(SUBJECTS)]
    if slug == "name" or "full name" in label or "applicant" in label or "guardian" in label or "parent" in label or "teacher" in label:
        return f"{fn} {ln}"
    if "roll" in label or slug.endswith("_no") or "code" in label or "reference" in label:
        return f"{entity_slug[:3].upper()}{2025000 + i}"
    if any(k in label for k in ("description", "note", "comment", "remark", "reason", "detail", "summary")):
        return f"{SUBJECTS[i % len(SUBJECTS)]} — record #{i + 1} for {entity_slug}."
    if "title" in label:
        return f"{entity_slug.replace('_', ' ').title()} {i + 1}"
    return f"{entity_slug.replace('_', ' ').title()} {i + 1}"


def create(entity, member, ws, data):
    return RecordService.create_record(workspace_id=ws.id, member=member, entity=entity, data=data)["id"]


def topo_order(ents, fld):
    """Order entities so an entity comes after the entities its lookups target."""
    deps = {}
    for s in ents:
        d = set()
        for f in fld[s]:
            if f.field_type in ("lookup", "relation", "user", "multirelation", "multiuser"):
                t = (f.config or {}).get("target_entity_slug") or (f.config or {}).get("target_entity")
                if t in ents and t != s:
                    d.add(t)
        deps[s] = d
    order, placed = [], set()
    for _ in range(len(ents) + 2):
        for s in ents:
            if s not in placed and deps[s] <= placed:
                order.append(s)
                placed.add(s)
        if len(placed) == len(ents):
            break
    order += [s for s in ents if s not in placed]  # leftover cycles
    return order


def fill(entity, fields, i, registry, overrides=None):
    data = {}
    for f in fields:
        v = generic_value(f, entity.slug, i, registry)
        if v is not None:
            data[f.slug] = v
    data.update(overrides or {})
    return data


def main():
    ws = Workspace.objects.get(slug=SLUG)
    member = WorkspaceMember.objects.filter(workspace_id=ws.id, role="owner").first() \
        or WorkspaceMember.objects.filter(workspace_id=ws.id).first()
    member.user = User.objects.get(id=member.user_id)

    ents = {e.slug: e for e in EntityDefinition.objects.filter(workspace_id=ws.id, is_active=True)}
    fld = {s: [f for f in FieldDefinition.objects.filter(entity_id=e.id, is_deleted=False)
               if f.is_promoted and f.field_type not in ("auto_number", "formula", "rollup")]
           for s, e in ents.items()}
    reg = {}

    def has(s):
        return s in ents

    with workspace_context(ws.id):
        # 1) academic year
        if has("academic_year"):
            reg["academic_year"] = [create(ents["academic_year"], member, ws,
                                           fill(ents["academic_year"], fld["academic_year"], 0, reg,
                                                {"name": "2025-2026", "is_current": True}))]
            print("  academic_year +1")
        # 2) terms
        if has("term"):
            reg["term"] = [create(ents["term"], member, ws, fill(ents["term"], fld["term"], k, reg,
                                  {"name": f"Term {k + 1}"})) for k in range(3)]
            print("  term +3")
        # 3) grade levels: Class 1..12
        if has("grade_level"):
            reg["grade_level"] = [create(ents["grade_level"], member, ws,
                                         fill(ents["grade_level"], fld["grade_level"], k, reg,
                                              {"name": f"Class {k + 1}"})) for k in range(12)]
            print("  grade_level +12 (Class 1-12)")
        # 4) subjects
        if has("subject"):
            reg["subject"] = [create(ents["subject"], member, ws, fill(ents["subject"], fld["subject"], k, reg,
                              {"name": SUBJECTS[k]})) for k in range(len(SUBJECTS))]
            print(f"  subject +{len(SUBJECTS)}")
        # 5) teachers (Indian names)
        if has("teacher"):
            tids = []
            for k in range(15):
                fn, ln, _ = person(k + 5)
                tids.append(create(ents["teacher"], member, ws,
                                   fill(ents["teacher"], fld["teacher"], k + 5, reg, {"name": f"{fn} {ln}"})))
            reg["teacher"] = tids
            print("  teacher +15")
        # 6) guardians (one per student → 120)
        if has("guardian"):
            gids = []
            for k in range(120):
                fn, ln, _ = person(k, female=(k % 2 == 1))
                gids.append(create(ents["guardian"], member, ws,
                                   fill(ents["guardian"], fld["guardian"], k, reg, {"name": f"{fn} {ln}"})))
            reg["guardian"] = gids
            print("  guardian +120")
        # 7) classes: Class 1-A .. Class 12-A
        cls_entity = "school_class" if has("school_class") else ("class" if has("class") else None)
        class_ids = []
        if cls_entity:
            for k in range(12):
                ov = {"name": f"Class {k + 1} - A"}
                if reg.get("grade_level"):
                    # set the grade_level lookup if the field exists
                    for f in fld[cls_entity]:
                        if f.field_type == "lookup" and (f.config or {}).get("target_entity_slug") == "grade_level":
                            ov[f.slug] = reg["grade_level"][k]
                class_ids.append(create(ents[cls_entity], member, ws,
                                        fill(ents[cls_entity], fld[cls_entity], k, reg, ov)))
            reg[cls_entity] = class_ids
            print(f"  {cls_entity} +12 (Class 1-12, section A)")
        # 8) students: 10 per class × 12 = 120
        if has("student") and class_ids:
            sids = []
            gi = 0
            for c, cid in enumerate(class_ids):
                for s in range(10):
                    n["i"] += 1
                    idx = c * 10 + s
                    fn, ln, gender = person(idx, female=(s % 2 == 0))
                    ov = {"first_name": fn, "last_name": ln, "gender": gender, "roll_no": str(s + 1),
                          "nationality": "India", "blood_group": BLOOD[idx % len(BLOOD)]}
                    # link guardian + class if those lookup fields exist
                    for f in fld["student"]:
                        if f.field_type == "lookup":
                            t = (f.config or {}).get("target_entity_slug")
                            if t == "guardian" and reg.get("guardian"):
                                ov[f.slug] = reg["guardian"][gi % len(reg["guardian"])]
                            elif t in (cls_entity,):
                                ov[f.slug] = cid
                    gi += 1
                    sids.append(create(ents["student"], member, ws,
                                       fill(ents["student"], fld["student"], idx, reg, ov)))
            reg["student"] = sids
            print(f"  student +{len(sids)} (12 classes × 10)")

        # 9) EVERY remaining entity gets data too (dependency-ordered, lookups resolved)
        print("  --- seeding all remaining entities ---")
        for s in topo_order(set(ents), fld):
            if s in reg:  # already seeded above
                continue
            ok = 0
            ids = []
            for k in range(10):
                n["i"] += 1
                try:
                    ids.append(create(ents[s], member, ws, fill(ents[s], fld[s], n["i"], reg)))
                    ok += 1
                except Exception as e:  # noqa: BLE001
                    if k == 0:
                        print(f"    {s:26s} FAILED: {str(e)[:80]}")
                        break
            reg[s] = ids
            if ok:
                print(f"    {s:26s} +{ok}")

    total = sum(len(v) for v in reg.values())
    seeded = sum(1 for v in reg.values() if v)
    print(f"done — Indian school seeded: {seeded}/{len(ents)} entities have data, {total} records total")


if __name__ == "__main__":
    main()
