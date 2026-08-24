"""Phase 3 (company structure) + Phase 5 (core master data) — created ONCE via REST.
Disposable operator script. Saves all IDs to state/master.json for 50-day continuity."""
import json, random, sys, time
from client import Api, ok
from schema_cache import discover
random.seed(42)
a = Api()
DAY = 0  # structure/master created before Day 1
M = {"customers": [], "vendors": [], "employees": [], "items": [], "warehouses": [],
     "departments": [], "branches": [], "item_categories": [], "asset_categories": [],
     "ticket_categories": [], "projects": [], "leave_types": []}
fail = []
def crt(path, payload, bucket=None, key="id", label=""):
    r = a.post(path, payload)
    if ok(r):
        try: rid = r.json().get(key)
        except Exception: rid = None
        if bucket is not None and rid: M[bucket].append(rid)
        return r.json() if rid else r
    fail.append({"path": path, "status": r.status_code, "body": r.text[:200], "label": label})
    return None

t0 = time.time()
# ---------- company structure ----------
discover("branch", "/api/v1/data/branch/", DAY)
HQ = ["Head Office","Dubai Branch","Riyadh Branch","Doha Branch","Kuwait Branch","Manama Branch"]
for i,n in enumerate(HQ):
    crt("/api/v1/data/branch/", {"code": f"BR{i:02d}", "name": n, "country": "AE",
        "timezone": "Asia/Dubai", "status": "active"}, "branches")

discover("department", "/api/v1/data/department/", DAY)
DEPTS = ["Sales","Marketing","CRM","Finance","Accounting","Procurement","Inventory",
 "Manufacturing","Quality","HR","Payroll","IT","Administration","Projects","Helpdesk",
 "Customer Success","Security","Legal","Operations","Maintenance","Logistics","Planning",
 "Analytics","Executive Office"]
for i,n in enumerate(DEPTS):
    crt("/api/v1/data/department/", {"code": f"D{i:02d}", "name": n, "status": "active"}, "departments")

# warehouses + locations (inventory native)
discover("warehouse", "/api/v1/inventory/warehouses/", DAY)
for i in range(10):
    w = crt(f"/api/v1/inventory/warehouses/", {"code": f"WH{i:02d}", "name": f"Warehouse {i:02d}", "is_active": True}, "warehouses")
    if w:
        for L in ("A","B"):
            a.post("/api/v1/inventory/locations/", {"warehouse": w["id"], "code": f"WH{i:02d}-{L}", "name": f"Zone {L}"})

# item categories
discover("item_category", "/api/v1/inventory/categories/", DAY)
for c in ["Raw Materials","Components","Finished Goods","Packaging","Consumables","Spare Parts",
          "Electronics","Hardware","Chemicals","Tools","Office Supplies","Logistics"]:
    cc = crt("/api/v1/inventory/categories/", {"name": c}, "item_categories")

# leave types
discover("leave_type", "/api/v1/data/leave_type/", DAY)
for code,n,d in [("AL","Annual Leave",30),("SL","Sick Leave",15),("CL","Casual Leave",7),
                 ("ML","Maternity Leave",90),("UL","Unpaid Leave",0)]:
    crt("/api/v1/data/leave_type/", {"code":code,"name":n,"default_days":d}, "leave_types")

# holiday calendar
discover("holiday_calendar", "/api/v1/data/holiday_calendar/", DAY)
for d,n in [("2026-01-01","New Year"),("2026-12-02","National Day"),("2026-05-01","Labour Day"),
            ("2026-07-15","Eid"),("2026-12-25","Year End")]:
    a.post("/api/v1/data/holiday_calendar/", {"name":n,"date":d,"country":"AE","type":"public"})

# asset categories
discover("asset_category", "/api/v1/data/asset_category/", DAY)
for n,m,life in [("IT Equipment","straight_line",36),("Vehicles","declining_balance",60),
                 ("Machinery","straight_line",120),("Furniture","straight_line",84),
                 ("Buildings","straight_line",360),("Tools","straight_line",48)]:
    crt("/api/v1/data/asset_category/", {"name":n,"default_depreciation_method":m,
        "default_useful_life_months":life}, "asset_categories")

# ticket categories
discover("ticket_category", "/api/v1/data/ticket_category/", DAY)
for n,t in [("Hardware","hardware"),("Software","software"),("Access","access_request"),
            ("Network","incident"),("Billing","question"),("General","service_request")]:
    crt("/api/v1/data/ticket_category/", {"name":n,"category_type":t}, "ticket_categories")

# fiscal year + business hours (best-effort)
fy = a.post("/api/v1/ledger/fiscal-years/", {"code":"FY2026","name":"FY2026",
     "start_date":"2026-01-01","end_date":"2026-12-31"})
bh = a.post("/api/v1/sla/business-hours/", {"name":"Standard","timezone":"Asia/Dubai",
     "schedule":{"mon":["09:00","18:00"],"tue":["09:00","18:00"],"wed":["09:00","18:00"],
     "thu":["09:00","18:00"],"fri":["09:00","13:00"]},"holidays":["2026-12-02","2026-07-15"]})
print("fiscal-year", fy.status_code, "| business-hours", bh.status_code)

# ---------- core master data ----------
# Customers (CRM accounts)
discover("account", "/api/v1/crm/account/", DAY)
INDS=["Manufacturing","Retail","Tech","Healthcare","Construction","Logistics","Energy","Finance"]
for i in range(500):
    crt("/api/v1/crm/account/", {"name": f"Customer {i:04d} {random.choice(['LLC','Inc','Group','Co'])}",
        "industry": random.choice(INDS), "status": "active",
        "revenue": random.randint(50000, 5000000)}, "customers")

# Vendors (procurement, numbered)
discover("vendor", "/api/v1/procurement/vendor/", DAY)
for i in range(200):
    crt("/api/v1/procurement/vendor/", {"vendor_code": f"V{i:04d}", "name": f"Vendor {i:04d} Supplies",
        "status": "active", "email": f"ap{i}@vendor.test"}, "vendors")

# Employees (HR)
discover("employee", "/api/v1/data/employee/", DAY)
FN=["Alex","Sam","Jordan","Taylor","Morgan","Casey","Riley","Jamie","Drew","Quinn","Lee","Noor","Omar","Sara","Ravi","Mei","Kofi","Ana","Yuki","Ivan"]
LN=["Khan","Ortiz","Diaz","Rao","Voss","Hall","Lim","Petrov","Mensah","Stone","Burke","Reyes","Berg","Faruk","Nair","Cruz","Cho","Roy","Haddad","Mills"]
ET=["permanent","contract","part_time","permanent","permanent"]
for i in range(100):
    crt("/api/v1/data/employee/", {"first_name": random.choice(FN), "last_name": random.choice(LN)+f"{i}",
        "email": f"emp{i:03d}@nexus.test", "hire_date": "2026-01-15",
        "employment_type": random.choice(ET), "status": "active",
        "department": random.choice(M["departments"]) if M["departments"] else None,
        "branch": random.choice(M["branches"]) if M["branches"] else None}, "employees")

# Products / items (inventory) — mix of raw + finished
discover("item", "/api/v1/inventory/items/", DAY)
VM=["average","fifo","standard"]
for i in range(400):
    cat = random.choice(M["item_categories"]) if M["item_categories"] else None
    crt("/api/v1/inventory/items/", {"sku": f"ITM-{i:04d}", "name": f"Product {i:04d}",
        "category": cat, "uom": "ea", "valuation_method": random.choice(VM),
        "standard_cost": str(round(random.uniform(2, 500), 2)), "track_inventory": True}, "items")

json.dump(M, open("E:/erp/sim/state/master.json","w"), indent=1)
json.dump(fail, open("E:/erp/sim/state/master_fail.json","w"), indent=1)
el = round(time.time()-t0)
print(f"\n=== MASTER DATA created in {el}s ===")
for k,v in M.items(): print(f"  {k}: {len(v)}")
print("FAILURES:", len(fail))
for f in fail[:8]: print("   ", f["label"] or f["path"], f["status"], f["body"][:120])
