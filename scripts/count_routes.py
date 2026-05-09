from erp.main import create_app
from collections import Counter

app = create_app()
domain_routes = Counter()
for r in app.routes:
    if hasattr(r, "path") and hasattr(r, "methods"):
        parts = r.path.split("/")
        if len(parts) >= 3:
            domain_routes[parts[2]] += 1

for domain, count in sorted(domain_routes.items(), key=lambda x: -x[1]):
    print(f"{domain:30s} {count:3d} routes")

print(f"\nTotal: {sum(domain_routes.values())} routes")
