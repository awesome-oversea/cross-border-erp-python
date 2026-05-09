import sys
sys.path.insert(0, "src")
from erp.main import app
routes = [r for r in app.routes if hasattr(r, "methods")]
print(f"Total routes: {len(routes)}")
for r in routes:
    if "connector" in r.path.lower():
        methods = ",".join(r.methods - {"HEAD", "OPTIONS"})
        print(f"  {methods:8s} {r.path}")
