import sys
sys.path.insert(0, "src")
try:
    from erp.main import app
    print("App created successfully!")
    routes = [r for r in app.routes if hasattr(r, "methods")]
    print(f"Total routes: {len(routes)}")
    for r in routes:
        methods = ",".join(r.methods - {"HEAD", "OPTIONS"})
        print(f"  {methods:8s} {r.path}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
