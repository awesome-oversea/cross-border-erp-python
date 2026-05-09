import sys, json, urllib.request
sys.stdout.reconfigure(line_buffering=True)

BASE = "http://localhost:8000"
TENANT_ID = "10a8a067-5004-417d-900c-f248a30d91fe"

def api_call(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json", "X-Tenant-ID": TENANT_ID}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(f"{BASE}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:300]
        return {"error": e.code, "body": err_body}

print("=== Step 1: 登录获取Token ===", flush=True)
login_result = api_call("POST", "/api/iam/v1/auth/login", {
    "tenant_id": TENANT_ID,
    "username": "admin",
    "password": "Admin@123"
})
if login_result.get("code") != 0:
    print(f"  LOGIN FAILED: {login_result}", flush=True)
    sys.exit(1)

token = login_result["data"]["access_token"]
print(f"  Token: {token[:50]}...", flush=True)
print(f"  User: {login_result['data'].get('display_name', 'N/A')}", flush=True)

print("\n=== Step 2: 获取当前用户信息 ===", flush=True)
result = api_call("GET", "/api/iam/v1/users/me", token=token)
print(f"  code={result.get('code', result.get('error'))}", flush=True)

print("\n=== Step 3: 创建核心业务数据 ===", flush=True)

tests = [
    ("创建仓库", "POST", "/api/wms/v1/warehouses", {
        "name": "深圳中心仓", "code": "WH-SZ-002", "type": "center",
        "address": "深圳市南山区科技园", "status": "active"
    }),
    ("创建供应商", "POST", "/api/scm/v1/suppliers", {
        "name": "深圳电子供应商", "code": "SUP-SZ-002", "status": "active"
    }),
    ("创建店铺", "POST", "/api/som/v1/stores", {
        "name": "Amazon US Store", "platform": "amazon", "code": "AMZ-US-002", "status": "active"
    }),
    ("创建物流商", "POST", "/api/tms/v1/providers", {
        "name": "DHL Express", "code": "DHL-002", "type": "express", "status": "active"
    }),
]

for name, method, path, data in tests:
    result = api_call(method, path, data, token=token)
    code = result.get("code", result.get("error"))
    print(f"  {name}: code={code}", flush=True)

print("\n=== Step 4: 查询所有域列表 ===", flush=True)
domains = [
    ("IAM Tenants", "/api/iam/v1/tenants"),
    ("IAM Users", "/api/iam/v1/users"),
    ("WMS Warehouses", "/api/wms/v1/warehouses"),
    ("WMS Inventory", "/api/wms/v1/inventory"),
    ("SCM Suppliers", "/api/scm/v1/suppliers"),
    ("CRM Customers", "/api/crm/v1/customers"),
    ("SOM Stores", "/api/som/v1/stores"),
    ("ADS Campaigns", "/api/ads/v1/campaigns"),
    ("OMS Orders", "/api/oms/v1/orders"),
    ("TMS Shipments", "/api/tms/v1/shipments"),
    ("FBA Shipments", "/api/fba/v1/shipments"),
    ("PDM SPUs", "/api/pdm/v1/spus"),
    ("FMS Cost Events", "/api/fms/v1/cost-events"),
    ("BI Metrics", "/api/bi/v1/metrics"),
    ("Dashboard KPI", "/api/dashboard/v1/kpi-overview"),
    ("SYS Statistics", "/api/sys/v1/statistics"),
]

ok_count = 0
fail_count = 0
for name, path in domains:
    result = api_call("GET", path, token=token)
    code = result.get("code", result.get("error", "?"))
    if code == 0:
        ok_count += 1
        items = result.get("data", {})
        if isinstance(items, dict):
            total = items.get("total", len(items.get("items", [])))
        elif isinstance(items, list):
            total = len(items)
        else:
            total = "?"
        print(f"  OK  {name}: total={total}", flush=True)
    else:
        fail_count += 1
        print(f"  FAIL {name}: code={code}", flush=True)

print(f"\n=== 端到端验证结果 ===", flush=True)
print(f"  成功: {ok_count}/{ok_count + fail_count}", flush=True)
print(f"  失败: {fail_count}/{ok_count + fail_count}", flush=True)

print("\n=== Step 5: 前端代理验证 ===", flush=True)
try:
    req = urllib.request.Request("http://localhost:3000/api/health")
    with urllib.request.urlopen(req, timeout=5) as resp:
        result = json.loads(resp.read().decode())
        print(f"  Frontend->Backend proxy: code={result.get('code')}", flush=True)
except Exception as e:
    print(f"  Frontend proxy error: {e}", flush=True)

print("\n=== 全流程验证完成 ===", flush=True)
