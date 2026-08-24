import json, time
from client import Api, ok
from dbread import scalar, q
a = Api()
WS = json.load(open("E:/erp/sim/state/roster.json"))["workspace_id"]

# 1) finish per-module configuration via supported /setup/ endpoints
SETUPS = ["crm","hr","payroll","projects","helpdesk","manufacturing","assets","analytics","procurement"]
setup_res = {}
for m in SETUPS:
    r = a.post(f"/api/v1/{m}/setup/")
    setup_res[m] = r.status_code
print("setup endpoints:", setup_res)

inst = json.load(open("E:/erp/sim/state/install_results.json"))
ents = json.load(open("E:/erp/sim/state/entities.json"))

# module -> entity slugs (rough grouping by known prefixes/sets)
from collections import defaultdict
# count entities provisioned overall
n_entities = len(ents)

# 2) accounting provisioning
accounts = a.get("/api/v1/ledger/accounts/").json()
rules = a.get("/api/v1/ledger/posting-rules/").json()
n_acct = len(accounts) if isinstance(accounts,list) else 0
n_rules = len(rules) if isinstance(rules,list) else 0

# 3) audit + domain events (read-only observation)
def safe_scalar(sql):
    try: return scalar(sql)
    except Exception as e: return f"ERR:{e}"
n_audit = safe_scalar("SELECT count(*) FROM audit_log") if True else None
# find domain events table name
try:
    ev_tbls = [r[0] for r in q("SELECT table_name FROM information_schema.tables WHERE table_name ILIKE '%event%'")]
except Exception as e:
    ev_tbls = [f"ERR:{e}"]
n_events = None
for t in ["domain_events","eventstore_domainevent"]:
    v = safe_scalar(f"SELECT count(*) FROM {t}")
    if isinstance(v,int): n_events=(t,v); break

# audit table name discovery
audit_tbls = []
try:
    audit_tbls = [r[0] for r in q("SELECT table_name FROM information_schema.tables WHERE table_name ILIKE '%audit%'")]
except Exception as e: audit_tbls=[f"ERR:{e}"]

print("\n=== INSTALL CERTIFICATION ===")
print("entities provisioned:", n_entities)
print("ledger accounts:", n_acct, "| posting rules:", n_rules)
print("event tables:", ev_tbls, "| domain events:", n_events)
print("audit tables:", audit_tbls)

# 4) module API visibility probes
probes = {
 "crm": "/api/v1/data/lead/", "procurement":"/api/v1/data/vendor/",
 "hr":"/api/v1/data/employee/", "projects":"/api/v1/data/project/",
 "helpdesk":"/api/v1/data/ticket/", "assets":"/api/v1/data/asset/",
 "manufacturing":"/api/v1/manufacturing/products/", "payroll":"/api/v1/payroll/components/",
 "analytics":"/api/v1/analytics/kpis/", "inventory":"/api/v1/inventory/items/",
 "ledger":"/api/v1/ledger/accounts/",
}
vis = {}
for m,p in probes.items():
    r=a.get(p); vis[m]=r.status_code
print("\nAPI visibility:", vis)
json.dump({"setup":setup_res,"n_entities":n_entities,"n_acct":n_acct,"n_rules":n_rules,
           "events":n_events,"audit_tables":audit_tbls,"event_tables":ev_tbls,"visibility":vis,
           "installs":inst}, open("E:/erp/sim/state/cert_install.json","w"), indent=2, default=str)
