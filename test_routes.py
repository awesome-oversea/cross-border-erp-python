import sys, json, urllib.request
sys.stdout.reconfigure(line_buffering=True)

endpoints = [
    "/api/health",
    "/api/iam/v1/tenants",
    "/api/oms/v1/orders",
    "/api/wms/v1/warehouses",
    "/api/scm/v1/suppliers",
    "/api/crm/v1/customers",
    "/api/tms/v1/shipments",
    "/api/fba/v1/shipments",
    "/api/pdm/v1/spus",
    "/api/som/v1/stores",
    "/api/ads/v1/campaigns",
    "/api/fms/v1/cost-events",
    "/api/bi/v1/metrics",
    "/api/sys/v1/dicts",
    "/api/dashboard/v1/kpi-overview",
]

headers = {"X-Tenant-ID": "test-tenant", "X-Actor-ID": "test-user"}

for ep in endpoints:
    try:
        req = urllib.request.Request(f"http://localhost:8000{ep}", headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            code = data.get("code", "?")
            msg = data.get("message", "?")[:50]
            print(f"  OK  {ep}  code={code} msg={msg}", flush=True)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:100]
        print(f"  {e.code}  {ep}  {body}", flush=True)
    except Exception as e:
        print(f"  ERR {ep}  {e}", flush=True)
