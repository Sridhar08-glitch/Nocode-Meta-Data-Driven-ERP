"""Operator HTTP client — the simulation's 'hands'. PURE REST client: it only
makes HTTP calls to the running NexusERP exactly as the frontend/customer does.
No business logic, no ORM, no DB writes. Shared by all simulation scripts."""
import json, time, requests

BASE = "http://127.0.0.1:8077"
STATE = "E:/erp/sim/state"

with open(f"{STATE}/roster.json") as f:
    ROSTER = json.load(f)

WS_SLUG = ROSTER["workspace_slug"]

class Api:
    def __init__(self, email=None, password=None, slug=WS_SLUG):
        self.email = email or ROSTER["admin_email"]
        self.password = password or ROSTER["password"]
        self.slug = slug
        self.s = requests.Session()
        self.access = None
        self.login()

    def login(self):
        r = self.s.post(f"{BASE}/api/v1/auth/login/",
                        json={"email": self.email, "password": self.password}, timeout=30)
        r.raise_for_status()
        data = r.json()
        self.access = data.get("access") or data.get("access_token") or data.get("token")
        if not self.access:
            raise RuntimeError(f"login: no access token in {data}")
        self.s.headers.update({
            "Authorization": f"Bearer {self.access}",
            "X-Workspace-Slug": self.slug,
            "Content-Type": "application/json",
        })
        return data

    def _u(self, path):
        return path if path.startswith("http") else f"{BASE}{path}"

    def req(self, method, path, **kw):
        kw.setdefault("timeout", 60)
        for attempt in range(2):
            r = self.s.request(method, self._u(path), **kw)
            if r.status_code == 401 and attempt == 0:
                self.login(); continue
            return r
        return r

    def get(self, path, **kw):   return self.req("GET", path, **kw)
    def post(self, path, payload=None, **kw):  return self.req("POST", path, data=json.dumps(payload or {}), **kw)
    def patch(self, path, payload=None, **kw): return self.req("PATCH", path, data=json.dumps(payload or {}), **kw)
    def delete(self, path, **kw): return self.req("DELETE", path, **kw)

def ok(r, *codes):
    codes = codes or (200, 201)
    return r.status_code in codes

if __name__ == "__main__":
    a = Api()
    print("login OK, token len", len(a.access))
    r = a.get("/api/v1/workspaces/")
    print("GET /workspaces/", r.status_code, r.json())
