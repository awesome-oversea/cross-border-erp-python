import sys, json, urllib.request
sys.stdout.reconfigure(line_buffering=True)

BASE = "http://localhost:3000"
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
        err_body = e.read().decode()[:500]
        return {"error": e.code, "body": err_body}

print("=== 前端代理端到端测试 ===", flush=True)

print("\n1. 健康检查 (通过前端代理)", flush=True)
result = api_call("GET", "/api/health")
print(f"   code={result.get('code')} status={result.get('data', {}).get('status', 'N/A')}", flush=True)

print("\n2. 登录 (通过前端代理)", flush=True)
result = api_call("POST", "/api/iam/v1/auth/login", {
    "tenant_id": TENANT_ID,
    "username": "admin",
    "password": "Admin@123"
})
if result.get("code") != 0:
    print(f"   LOGIN FAILED: {result}", flush=True)
    sys.exit(1)
token = result["data"]["access_token"]
print(f"   Token: {token[:40]}...", flush=True)
print(f"   User: {result['data'].get('display_name', 'N/A')}", flush=True)

print("\n3. 查询域数据 (通过前端代理 + Token认证)", flush=True)
domains = [
    ("IAM Users", "/api/iam/v1/users"),
    ("WMS Warehouses", "/api/wms/v1/warehouses"),
    ("SCM Suppliers", "/api/scm/v1/suppliers"),
    ("SOM Stores", "/api/som/v1/stores"),
    ("OMS Orders", "/api/oms/v1/orders"),
    ("Dashboard KPI", "/api/dashboard/v1/kpi-overview"),
    ("SYS Statistics", "/api/sys/v1/statistics"),
]

ok = 0
fail = 0
for name, path in domains:
    result = api_call("GET", path, token=token)
    code = result.get("code", result.get("error", "?"))
    if code == 0:
        ok += 1
        items = result.get("data", {})
        if isinstance(items, dict):
            total = items.get("total", len(items.get("items", [])))
        elif isinstance(items, list):
            total = len(items)
        else:
            total = "?"
        print(f"   OK  {name}: total={total}", flush=True)
    else:
        fail += 1
        print(f"   FAIL {name}: code={code}", flush=True)

print(f"\n=== 前端代理验证结果 ===", flush=True)
print(f"   通过: {ok}/{ok + fail}", flush=True)
print(f"   失败: {fail}/{ok + fail}", flush=True)
print(f"\n=== 全部验证完成 ===", flush=True)
