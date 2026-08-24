import json
from client import Api, ok
a = Api()
r = a.get("/api/v1/solution-templates/")
tpls = r.json()
print("templates available:", len(tpls))
for t in tpls:
    print(f"  {t.get('slug'):20} {t.get('id')}  category={t.get('category')} system={t.get('is_system')}")
with open("E:/erp/sim/state/templates.json","w") as f:
    json.dump(tpls, f, indent=2)
