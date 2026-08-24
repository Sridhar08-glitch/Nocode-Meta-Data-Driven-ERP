"""Just-in-time schema cache. Schemas were discovered ONCE (cached in fields.json);
this module serves them without ever re-fetching, and appends a SCHEMA_CACHE.md
entry the FIRST time an entity is used during the simulation."""
import json, os
_FIELDS = json.load(open("E:/erp/sim/state/fields.json"))
_SEEN_PATH = "E:/erp/sim/state/schema_seen.json"
_seen = set(json.load(open(_SEEN_PATH))) if os.path.exists(_SEEN_PATH) else set()
_MD = "E:/erp/ERP_SCHEMA_CACHE.md" if os.path.exists("E:/erp/ERP_SCHEMA_CACHE.md") else "E:/erp/SCHEMA_CACHE.md"

def schema(slug):
    return _FIELDS.get(slug, [])

def required(slug):
    return [f["slug"] for f in schema(slug) if isinstance(f, dict) and f.get("req")]

def choices(slug, field):
    for f in schema(slug):
        if isinstance(f, dict) and f.get("slug") == field:
            return f.get("choices")
    return None

def discover(slug, endpoint, day):
    """Record first use of an entity's schema in SCHEMA_CACHE.md (once)."""
    if slug in _seen:
        return
    _seen.add(slug)
    json.dump(sorted(_seen), open(_SEEN_PATH, "w"))
    fs = schema(slug)
    if isinstance(fs, dict):
        line = f"| {slug} | {endpoint} | (native/no metadata) | – | – | Day {day} |\n"
    else:
        names = ", ".join(f["slug"] for f in fs)
        req = ", ".join(f["slug"] for f in fs if f.get("req")) or "(none enforced)"
        sels = "; ".join(f"{f['slug']}={f['choices']}" for f in fs
                         if f.get("type") in ("select", "status") and f.get("choices"))
        line = f"| {slug} | {endpoint} | {names[:120]} | {req} | {sels[:120] or '–'} | Day {day} |\n"
    with open(_MD, "a", encoding="utf-8") as f:
        f.write(line)
