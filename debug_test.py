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
        err_body = e.read().decode()[:500]
        return {"error": e.code, "body": err_body}

login_result = api_call("POST", "/api/iam/v1/auth/login", {
    "tenant_id": TENANT_ID,
    "username": "admin",
    "password": "Admin@123"
})
token = login_result["data"]["access_token"]
print(f"Token: {token[:60]}...", flush=True)

print("\n=== Test /users/me ===", flush=True)
result = api_call("GET", "/api/iam/v1/users/me", token=token)
print(f"  Full response: {json.dumps(result, ensure_ascii=False)[:500]}", flush=True)

print("\n=== Test /tenants (no auth) ===", flush=True)
result = api_call("GET", "/api/iam/v1/tenants")
print(f"  Full response: {json.dumps(result, ensure_ascii=False)[:500]}", flush=True)

print("\n=== Test /warehouses (no auth) ===", flush=True)
result = api_call("GET", "/api/wms/v1/warehouses")
print(f"  Full response: {json.dumps(result, ensure_ascii=False)[:500]}", flush=True)
