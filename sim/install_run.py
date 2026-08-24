import json, time
from client import Api, ok
a = Api()
tpls = {t["slug"]: t for t in json.load(open("E:/erp/sim/state/templates.json"))}
ORDER = ["crm","procurement","hr","projects","helpdesk","assets","manufacturing","payroll","analytics"]
results = {}
for slug in ORDER:
    t = tpls[slug]
    r = a.post(f"/api/v1/solution-templates/{t['id']}/install/")
    body = {}
    try: body = r.json()
    except Exception: body = {"raw": r.text[:300]}
    results[slug] = {"status": r.status_code, "ok": ok(r), "detail": body if not ok(r) else "installed"}
    print(f"{slug:14} -> {r.status_code} {'OK' if ok(r) else body}")
    time.sleep(0.3)
json.dump(results, open("E:/erp/sim/state/install_results.json","w"), indent=2)
# Now list all installed solutions + all entities
inst = a.get("/api/v1/solution-templates/installed/").json()
print("\nINSTALLED SOLUTIONS:", [i.get("template_slug") or i.get("slug") for i in inst] if isinstance(inst,list) else inst)
ents = a.get("/api/v1/metadata/entities/").json()
ent_list = ents if isinstance(ents, list) else ents.get("results", ents)
slugs = sorted([e.get("slug") for e in ent_list])
print("\nENTITIES PROVISIONED:", len(slugs))
print(slugs)
json.dump(ent_list, open("E:/erp/sim/state/entities.json","w"), indent=2)
