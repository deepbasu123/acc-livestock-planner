#!/usr/bin/env python3
"""
ACC Livestock Planner - one-command deployer.

Provisions the whole demo into a Databricks workspace you control:
  catalog + schemas + volume -> synthetic data -> gold views -> ABAC masks
  -> Genie space -> AI/BI dashboard -> (optionally) the Databricks App.

It is parameterised entirely by environment variables (see config.example.sh).
Re-running is safe: SQL objects use CREATE OR REPLACE / IF NOT EXISTS and the
data load truncates-and-replaces.

Usage:
    source config.example.sh          # after editing it for your workspace
    databricks auth login --profile $ACC_PROFILE   # if not already authed
    python3 deploy.py                 # full data + analytics deploy
    python3 deploy.py --with-app      # also build + deploy the Databricks App
    python3 deploy.py --only data     # run a single phase: data|gold|genie|dashboard|app

Prereqs: Python 3.10+, the Databricks CLI on PATH, and (for --with-app) Node 18+.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "sql"))
import dbsql  # noqa: E402  (reads ACC_* env)

PROFILE = os.environ.get("ACC_PROFILE", "DEFAULT")
CATALOG = os.environ.get("ACC_CATALOG", "")
WAREHOUSE = os.environ.get("ACC_WAREHOUSE", "")
HOST = os.environ.get("ACC_HOST", "")
PARENT = os.environ.get("ACC_PARENT", "/Workspace/Shared/acc-livestock-planner")
LLM_MODEL = os.environ.get("ACC_LLM_MODEL", "databricks-claude-sonnet-4-6")
APP_NAME = os.environ.get("ACC_APP_NAME", "acc-livestock-planner")
# Lakebase (operational Postgres) - operational data system of record for the app.
LAKEBASE_PROJECT = os.environ.get("ACC_LAKEBASE_PROJECT", "acc-livestock-planner")
PG_SCHEMA = os.environ.get("ACC_PG_SCHEMA", "acc")

SCHEMAS = ["acc_feedlot", "acc_counterparty", "acc_reference", "acc_booking", "acc_audit", "acc_gold"]
# Operational tables the app owns in Lakebase Postgres; seeded from the same
# synthetic generator that loads the Delta analytics layer.
PG_SEED_TABLES = [
    ("acc_feedlot", "feedlots"),
    ("acc_counterparty", "agents"), ("acc_counterparty", "vendors"),
    ("acc_counterparty", "payees"), ("acc_counterparty", "buyers"),
    ("acc_reference", "programs"), ("acc_reference", "weigh_points"), ("acc_reference", "origins"),
    ("acc_booking", "cattle_bookings"),
    ("acc_audit", "booking_history"),
]
SEED_DIR = ROOT / "app" / "server" / "seed"
VOL_ROOT = f"/Volumes/{CATALOG}/acc_gold/staging"
LOAD_ROOT = f"{VOL_ROOT}/load"


def log(msg):
    print(f"\n\033[1;36m== {msg}\033[0m", flush=True)


def sh(args, **kw):
    print(f"  $ {' '.join(args)}")
    return subprocess.run(args, check=True, **kw)


def cli(*args):
    return ["databricks", *args, "--profile", PROFILE]


def require_env():
    missing = [k for k in ("ACC_WAREHOUSE",) if not os.environ.get(k)]
    if missing:
        sys.exit(f"Missing required env: {', '.join(missing)}. See config.example.sh")
    log("Config")
    print(f"  profile   : {PROFILE}")
    print(f"  catalog   : {CATALOG}")
    print(f"  warehouse : {WAREHOUSE}")
    print(f"  parent    : {PARENT}")
    print(f"  llm model : {LLM_MODEL}")
    # auth sanity check
    me = subprocess.run(cli("current-user", "me"), capture_output=True, text=True)
    if me.returncode != 0:
        sys.exit(f"Not authenticated for profile '{PROFILE}'. Run: databricks auth login --profile {PROFILE}\n{me.stderr}")
    print(f"  authed as : ok")


def run_sql_file(name):
    text = (ROOT / "sql" / name).read_text()
    text = text.replace("project_command_centre", CATALOG)
    n = dbsql.run_script(text, catalog=CATALOG)
    print(f"  ran {n} statements from {name}")


def upload_tree(local_dir: Path, dest_root: str):
    """Recursively copy each schema folder to the volume (fs cp -r creates dirs)."""
    schema_dirs = sorted(d for d in local_dir.iterdir() if d.is_dir())
    print(f"  uploading {len(schema_dirs)} schema folders to {dest_root}")
    for d in schema_dirs:
        dest = f"dbfs:{dest_root}/{d.name}"
        r = subprocess.run(cli("fs", "cp", "-r", str(d), dest, "--overwrite"),
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"upload failed for {d.name}: {r.stderr.strip()}")
        print(f"    {d.name}/ ok")
    print("  upload complete")


# ---------------------------------------------------------------- phases
def phase_provision():
    log("Provisioning catalog / schemas / volume")
    try:
        dbsql.run(f"CREATE CATALOG IF NOT EXISTS {CATALOG}", catalog=None)
    except Exception as e:
        print(f"  ! could not CREATE CATALOG ({e}).")
        print(f"  ! Pre-create the catalog or point ACC_CATALOG at an existing one, then re-run.")
        # verify it at least exists/usable
        dbsql.run(f"USE CATALOG {CATALOG}", catalog=None)
    for s in SCHEMAS:
        dbsql.run(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{s}", catalog=None)
    dbsql.run(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.acc_gold.staging", catalog=None)
    ensure_parent()
    print(f"  catalog, {len(SCHEMAS)} schemas, staging volume and workspace folder ready")


def write_pg_seed():
    """Convert the generated parquet into JSONL the app self-seeds Lakebase from
    on first startup (stdlib json load, no pandas at runtime). Generated at
    deploy time, never committed."""
    import json as _json
    import datetime as _dt
    import pandas as _pd
    import numpy as _np

    def _clean(v):
        if isinstance(v, (list, dict)):
            return v
        try:
            if _pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        if isinstance(v, (_pd.Timestamp, _dt.datetime, _dt.date)):
            return v.isoformat()
        if isinstance(v, _np.integer):
            return int(v)
        if isinstance(v, _np.floating):
            return float(v)
        if isinstance(v, _np.bool_):
            return bool(v)
        return v

    SEED_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for schema, table in PG_SEED_TABLES:
        df = _pd.read_parquet(ROOT / "data_gen" / "out" / schema / f"{table}.parquet")
        recs = [{k: _clean(v) for k, v in r.items()} for r in df.to_dict(orient="records")]
        with open(SEED_DIR / f"{table}.jsonl", "w") as f:
            for r in recs:
                f.write(_json.dumps(r) + "\n")
        total += len(recs)
    print(f"  wrote Lakebase seed: {len(PG_SEED_TABLES)} tables, {total} rows -> {SEED_DIR}")


def phase_data():
    log("Generating + loading source data")
    sh([sys.executable, str(ROOT / "data_gen" / "generate.py")])
    upload_tree(ROOT / "data_gen" / "out", LOAD_ROOT)
    sh([sys.executable, str(ROOT / "sql" / "load_tables.py")])
    write_pg_seed()


def phase_gold():
    log("Building gold views + ABAC classification/masks")
    run_sql_file("02_gold_views.sql")
    run_sql_file("03_classification_abac.sql")


def _cli_json(*args):
    r = subprocess.run(cli(*args, "-o", "json"), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"databricks {' '.join(args)} failed: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout) if r.stdout.strip() else {}


def _items(resp, key):
    if isinstance(resp, list):
        return resp
    return resp.get(key, []) or []


def phase_lakebase():
    """Provision (or reuse) the Lakebase Autoscaling project that backs the app's
    operational data, and return the connection resource paths + host. Idempotent."""
    log("Provisioning Lakebase (operational Postgres)")
    proj = f"projects/{LAKEBASE_PROJECT}"
    existing = [p.get("name") for p in _items(_cli_json("postgres", "list-projects"), "projects")]
    if proj in existing:
        print(f"  reusing Lakebase project {proj}")
    else:
        print(f"  creating Lakebase project {proj}")
        subprocess.run(cli("postgres", "create-project", LAKEBASE_PROJECT,
                           "--json", json.dumps({"spec": {"display_name": APP_NAME}})),
                       check=True)
    # Discover the production branch, its read-write endpoint + host, and the DB.
    branch = _items(_cli_json("postgres", "list-branches", proj), "branches")[0]["name"]
    endpoints = _items(_cli_json("postgres", "list-endpoints", branch), "endpoints")
    ep = next((e for e in endpoints if (e.get("spec") or {}).get("type") == "ENDPOINT_TYPE_READ_WRITE"), endpoints[0])
    ep_name = ep["name"]
    host = ((ep.get("status") or {}).get("hosts") or {}).get("host")
    if not host:  # freshly created endpoints populate host a moment later
        host = ((_cli_json("postgres", "get-endpoint", ep_name).get("status") or {}).get("hosts") or {}).get("host")
    dbs = _items(_cli_json("postgres", "list-databases", branch), "databases")
    db = dbs[0]
    lakebase = {
        "project": proj, "branch": branch, "endpoint": ep_name, "database": db["name"],
        "host": host, "pg_db": (db.get("status") or {}).get("postgres_database", "databricks_postgres"),
        "schema": PG_SCHEMA,
    }
    print(f"  endpoint : {ep_name}")
    print(f"  host     : {host}")
    print(f"  database : {db['name']}")
    return lakebase


def ensure_parent():
    """Create the workspace folder Genie / dashboard / app source live under."""
    subprocess.run(cli("workspace", "mkdirs", PARENT), capture_output=True, text=True)


def phase_genie():
    log("Creating Genie space")
    ensure_parent()
    out = subprocess.run([sys.executable, str(ROOT / "genie" / "build_genie.py")],
                         capture_output=True, text=True)
    print(out.stdout)
    if out.returncode != 0:
        sys.exit(out.stderr)
    sid = _grep(out.stdout, "SPACE_ID:")
    print(f"  GENIE SPACE: {sid}")
    return sid


def phase_dashboard():
    log("Creating AI/BI dashboard")
    ensure_parent()
    out = subprocess.run([sys.executable, str(ROOT / "dashboard" / "build_dashboard.py")],
                         capture_output=True, text=True)
    print(out.stdout)
    if out.returncode != 0:
        sys.exit(out.stderr)
    did = _grep(out.stdout, "DASHBOARD_ID:")
    print(f"  DASHBOARD: {did}")
    return did


def phase_app(genie_id, dashboard_id, lakebase):
    log("Building + deploying the Databricks App (Lakebase-backed)")
    from app import deploy_app  # app/deploy_app.py
    deploy_app.main(profile=PROFILE, catalog=CATALOG, warehouse=WAREHOUSE,
                    genie_id=genie_id, dashboard_id=dashboard_id,
                    llm_model=LLM_MODEL, app_name=APP_NAME, root=ROOT, lakebase=lakebase)


def _grep(text, prefix):
    for line in text.splitlines():
        if line.strip().startswith(prefix):
            return line.split(prefix, 1)[1].strip()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-app", action="store_true", help="also build + deploy the Databricks App")
    ap.add_argument("--only", choices=["data", "gold", "lakebase", "genie", "dashboard", "app"],
                    help="run a single phase (assumes prior phases already ran)")
    args = ap.parse_args()

    require_env()

    if args.only:
        if args.only == "data":
            phase_provision(); phase_data()
        elif args.only == "gold":
            phase_gold()
        elif args.only == "lakebase":
            phase_lakebase()
        elif args.only == "genie":
            print(phase_genie())
        elif args.only == "dashboard":
            print(phase_dashboard())
        elif args.only == "app":
            lakebase = phase_lakebase()
            phase_app(os.environ.get("ACC_GENIE_SPACE", ""), os.environ.get("ACC_DASHBOARD", ""), lakebase)
        return

    phase_provision()
    phase_data()
    phase_gold()
    genie_id = phase_genie()
    dashboard_id = phase_dashboard()
    lakebase = phase_lakebase()

    log("Analytics + Lakebase layer deployed")
    print(f"  Genie space     : {genie_id}")
    print(f"  Dashboard       : {dashboard_id}")
    print(f"  Lakebase project: {lakebase['project']}")
    print(f"  Set these in app/app.yaml (or pass --with-app to do it automatically):")
    print(f"    ACC_GENIE_SPACE = {genie_id}")
    print(f"    ACC_DASHBOARD   = {dashboard_id}")

    if args.with_app:
        phase_app(genie_id, dashboard_id, lakebase)
    else:
        print("\n  (App not deployed. Re-run with --with-app, or follow the README.)")


if __name__ == "__main__":
    main()
