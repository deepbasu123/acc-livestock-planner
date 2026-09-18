#!/usr/bin/env python3
"""
Build and deploy the Project Command Centre Databricks App.

Called by ../deploy.py --with-app, or standalone:
    python3 app/deploy_app.py

Flow:
  1. build the React frontend (npm ci && npm run build) -> frontend/dist
  2. write app.yaml with the resolved catalog / warehouse / genie / dashboard / model
  3. create the app (REST) if it doesn't exist
  4. sync source to a workspace folder and deploy
  5. grant the app's service principal the UC / warehouse / Genie access it needs

Env (when run standalone): ACC_PROFILE, ACC_CATALOG, ACC_WAREHOUSE, ACC_GENIE_SPACE,
ACC_DASHBOARD, ACC_LLM_MODEL, ACC_APP_NAME, ACC_PARENT.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _run(args, **kw):
    print(f"  $ {' '.join(args)}")
    return subprocess.run(args, **kw)


def _api(profile, method, path, body=None):
    args = ["databricks", "api", method, path, "--profile", profile]
    if body is not None:
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(body, f)
        f.close()
        args += ["--json", f"@{f.name}"]
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"{method} {path} failed: {p.stderr[:500]}")
    return json.loads(p.stdout) if p.stdout.strip() else {}


def write_app_yaml(root, catalog, warehouse, genie_id, dashboard_id, llm_model):
    yaml = f"""command:
  - "python"
  - "-m"
  - "uvicorn"
  - "app:app"
  - "--host"
  - "0.0.0.0"
  - "--port"
  - "8000"

env:
  - name: ACC_CATALOG
    value: "{catalog}"
  - name: ACC_WAREHOUSE
    value: "{warehouse}"
  - name: ACC_GENIE_SPACE
    value: "{genie_id}"
  - name: ACC_DASHBOARD
    value: "{dashboard_id}"
  - name: ACC_LLM_MODEL
    value: "{llm_model}"
"""
    (root / "app" / "app.yaml").write_text(yaml)
    print("  wrote app/app.yaml")


def build_frontend(root):
    fe = root / "app" / "frontend"
    npm = "npm"
    lock = fe / "package-lock.json"
    _run([npm, "ci" if lock.exists() else "install"], cwd=fe, check=True)
    _run([npm, "run", "build"], cwd=fe, check=True)
    if not (fe / "dist" / "index.html").exists():
        sys.exit("frontend build did not produce dist/index.html")
    print("  frontend built")


def ensure_app(profile, name):
    try:
        app = _api(profile, "get", f"/api/2.0/apps/{name}")
        print(f"  app '{name}' exists")
        return app
    except RuntimeError:
        print(f"  creating app '{name}'")
        _api(profile, "post", "/api/2.0/apps", {"name": name})
        # wait for it to leave CREATING
        for _ in range(60):
            app = _api(profile, "get", f"/api/2.0/apps/{name}")
            if app.get("compute_status", {}).get("state") not in ("STARTING", None) or app.get("service_principal_client_id"):
                return app
            time.sleep(5)
        return _api(profile, "get", f"/api/2.0/apps/{name}")


def wait_running(profile, name, timeout=900):
    """Apps must have ACTIVE compute before the first deployment. Start if stopped, then poll."""
    waited = 0
    while waited < timeout:
        app = _api(profile, "get", f"/api/2.0/apps/{name}")
        state = app.get("compute_status", {}).get("state")
        if state == "ACTIVE":
            print("  app compute ACTIVE")
            return
        if state == "STOPPED":
            try:
                _api(profile, "post", f"/api/2.0/apps/{name}/start")
            except RuntimeError:
                pass
        print(f"  waiting for app compute (state={state})...")
        time.sleep(15)
        waited += 15
    print("  ! app compute did not reach ACTIVE in time; trying deploy anyway")


def sync_and_deploy(profile, name, root, parent):
    src = root / "app"
    ws_path = f"{parent}/app"
    _run(["databricks", "sync", str(src), ws_path, "--profile", profile, "--full"], check=True)
    print(f"  synced source to {ws_path}")
    # `databricks sync` honours .gitignore, which excludes the built frontend
    # (frontend/dist). Push it explicitly so the app can serve the SPA.
    dist = src / "frontend" / "dist"
    if dist.is_dir():
        _run(["databricks", "workspace", "import-dir", str(dist),
              f"{ws_path}/frontend/dist", "--overwrite", "--profile", profile], check=True)
        print("  uploaded frontend/dist")
    dep = _api(profile, "post", f"/api/2.0/apps/{name}/deployments", {"source_code_path": ws_path})
    print(f"  deployment submitted: {dep.get('deployment_id', dep)}")
    return ws_path


def grant_sp(profile, catalog, warehouse, genie_id, sp):
    """Grant the app service principal the access it needs. Best-effort, idempotent."""
    if not sp:
        print("  ! could not resolve app service principal; grant access manually")
        return
    import sys as _s
    _s.path.insert(0, str(Path(__file__).resolve().parent.parent / "sql"))
    import dbsql
    # The app writes to acc_counterparty/acc_reference (master data admin) and
    # acc_booking/acc_audit (booking CRUD + history); acc_feedlot and acc_gold
    # are read-only from the app's perspective. Forgetting MODIFY here is a
    # real failure mode: reads all succeed (fooling a quick smoke test) while
    # every create/update/delete/duplicate call 500s in production.
    ALL_SCHEMAS = ["acc_feedlot", "acc_counterparty", "acc_reference", "acc_booking", "acc_audit", "acc_gold"]
    WRITE_SCHEMAS = ["acc_counterparty", "acc_reference", "acc_booking", "acc_audit"]
    grants = [
        f"GRANT USE CATALOG ON CATALOG {catalog} TO `{sp}`",
    ]
    for s in ALL_SCHEMAS:
        grants.append(f"GRANT USE SCHEMA ON SCHEMA {catalog}.{s} TO `{sp}`")
        grants.append(f"GRANT SELECT ON SCHEMA {catalog}.{s} TO `{sp}`")
    for s in WRITE_SCHEMAS:
        grants.append(f"GRANT MODIFY ON SCHEMA {catalog}.{s} TO `{sp}`")
    grants.append(f"GRANT EXECUTE ON SCHEMA {catalog}.acc_gold TO `{sp}`")
    for g in grants:
        try:
            dbsql.run(g, catalog=None, quiet=True)
        except Exception as e:
            print(f"  ! grant failed: {g} :: {e}")
    print(f"  UC grants applied to {sp}")
    # warehouse CAN_USE
    try:
        _api(profile, "patch", f"/api/2.0/permissions/warehouses/{warehouse}",
             {"access_control_list": [{"service_principal_name": sp, "permission_level": "CAN_USE"}]})
        print("  warehouse CAN_USE granted")
    except Exception as e:
        print(f"  ! warehouse grant failed: {e}")
    # genie CAN_RUN
    if genie_id:
        try:
            _api(profile, "patch", f"/api/2.0/permissions/genie/{genie_id}",
                 {"access_control_list": [{"service_principal_name": sp, "permission_level": "CAN_RUN"}]})
            print("  Genie CAN_RUN granted")
        except Exception as e:
            print(f"  ! genie grant failed: {e}")


def main(profile=None, catalog=None, warehouse=None, genie_id=None, dashboard_id=None,
         llm_model=None, app_name=None, root=None):
    profile = profile or os.environ.get("ACC_PROFILE", "DEFAULT")
    catalog = catalog or os.environ.get("ACC_CATALOG", "deep_test_1_catalog")
    warehouse = warehouse or os.environ["ACC_WAREHOUSE"]
    genie_id = genie_id or os.environ.get("ACC_GENIE_SPACE", "")
    dashboard_id = dashboard_id or os.environ.get("ACC_DASHBOARD", "")
    llm_model = llm_model or os.environ.get("ACC_LLM_MODEL", "databricks-claude-sonnet-4-6")
    app_name = app_name or os.environ.get("ACC_APP_NAME", "acc-livestock-planner")
    parent = os.environ.get("ACC_PARENT", "/Workspace/Shared/acc-livestock-planner")
    root = Path(root) if root else Path(__file__).resolve().parent.parent

    write_app_yaml(root, catalog, warehouse, genie_id, dashboard_id, llm_model)
    build_frontend(root)
    ensure_app(profile, app_name)
    wait_running(profile, app_name)
    sync_and_deploy(profile, app_name, root, parent)
    # re-fetch: the service principal is populated once the app finishes provisioning
    app = _api(profile, "get", f"/api/2.0/apps/{app_name}")
    sp = app.get("service_principal_client_id") or app.get("service_principal_name")
    grant_sp(profile, catalog, warehouse, genie_id, sp)
    url = app.get("url") or f"(check: databricks apps get {app_name})"
    print(f"\n  App deploying. URL: {url}")
    print(f"  Service principal: {sp}")
    print("  Note: for the persona demo to show UNMASKED data, add this SP and yourself to")
    print("  the workspace groups acc_exec / acc_procurement / acc_operations (see README).")


if __name__ == "__main__":
    main()
