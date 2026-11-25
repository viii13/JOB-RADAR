import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root.parent))

from job_market.api import create_app

app = create_app()

print("EXPANDED ROUTE TREE:")

endpoint_list = []

for i, r in enumerate(app.routes):
    cls_name = type(r).__name__
    if hasattr(r, "path") and hasattr(r, "methods"):
        methods = sorted(list(r.methods))
        print(f"Direct Route {i:02d}: {r.path} {methods}")
        if not r.path.startswith("/docs") and not r.path.startswith("/openapi") and not r.path.startswith("/redoc"):
            endpoint_list.append(("Direct App (api.py)", r.path, methods))
    elif hasattr(r, "router") or hasattr(r, "routes"):
        sub_routes = getattr(r, "routes", getattr(getattr(r, "router", None), "routes", []))
        print(f"Included Router {i:02d} ({cls_name}) with {len(sub_routes)} subroutes:")
        for sub in sub_routes:
            sub_methods = sorted(list(getattr(sub, "methods", [])))
            print(f"   -> {sub.path} {sub_methods}")
            endpoint_list.append((f"Included Router ({cls_name})", sub.path, sub_methods))

print("\n--- ALL BUSINESS/API ENDPOINTS (Excluding docs/openapi) ---")
for idx, (source, path, methods) in enumerate(sorted(endpoint_list, key=lambda x: x[1])):
    print(f"{idx+1:02d}. [{', '.join(methods)}] {path} ({source})")
print(f"\nTotal Business Endpoints: {len(endpoint_list)}")
