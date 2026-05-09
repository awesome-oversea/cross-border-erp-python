import sys
sys.stdout.reconfigure(line_buffering=True)
try:
    from erp.main import app
    print(f"App created: {app.title}", flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)
    import traceback
    traceback.print_exc()
