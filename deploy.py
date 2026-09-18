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
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "sql"))
import dbsql  # noqa: E402  (reads ACC_* env)

PROFILE = os.environ.get("ACC_PROFILE", "DEFAULT")
CATALOG = os.environ.get("ACC_CATALOG", "deep_test_1_catalog")
WAREHOUSE = os.environ.get("ACC_WAREHOUSE", "")
HOST = os.environ.get("ACC_HOST", "")
PARENT = os.environ.get("ACC_PARENT", "/Workspace/Shared/acc-livestock-planner")
LLM_MODEL = os.environ.get("ACC_LLM_MODEL", "databricks-claude-sonnet-4-6")
APP_NAME = os.environ.get("ACC_APP_NAME", "acc-livestock-planner")

SCHEMAS = ["acc_feedlot", "acc_counterparty", "acc_reference", "acc_booking", "acc_audit", "acc_gold"]
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


def phase_data():
    log("Generating + loading source data")
    sh([sys.executable, str(ROOT / "data_gen" / "generate.py")])
    upload_tree(ROOT / "data_gen" / "out", LOAD_ROOT)
    sh([sys.executable, str(ROOT / "sql" / "load_tables.py")])


def phase_gold():
    log("Building gold views + ABAC classification/masks")
    run_sql_file("02_gold_views.sql")
    run_sql_file("03_classification_abac.sql")


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


def phase_app(genie_id, dashboard_id):
    log("Building + deploying the Databricks App")
    from app import deploy_app  # app/deploy_app.py
    deploy_app.main(profile=PROFILE, catalog=CATALOG, warehouse=WAREHOUSE,
                    genie_id=genie_id, dashboard_id=dashboard_id,
                    llm_model=LLM_MODEL, app_name=APP_NAME, root=ROOT)


def _grep(text, prefix):
    for line in text.splitlines():
        if line.strip().startswith(prefix):
            return line.split(prefix, 1)[1].strip()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-app", action="store_true", help="also build + deploy the Databricks App")
    ap.add_argument("--only", choices=["data", "gold", "genie", "dashboard", "app"],
                    help="run a single phase (assumes prior phases already ran)")
    args = ap.parse_args()

    require_env()

    if args.only:
        if args.only == "data":
            phase_provision(); phase_data()
        elif args.only == "gold":
            phase_gold()
        elif args.only == "genie":
            print(phase_genie())
        elif args.only == "dashboard":
            print(phase_dashboard())
        elif args.only == "app":
            phase_app(os.environ.get("ACC_GENIE_SPACE", ""), os.environ.get("ACC_DASHBOARD", ""))
        return

    phase_provision()
    phase_data()
    phase_gold()
    genie_id = phase_genie()
    dashboard_id = phase_dashboard()

    log("Analytics layer deployed")
    print(f"  Genie space : {genie_id}")
    print(f"  Dashboard   : {dashboard_id}")
    print(f"  Set these in app/app.yaml (or pass --with-app to do it automatically):")
    print(f"    ACC_GENIE_SPACE = {genie_id}")
    print(f"    ACC_DASHBOARD   = {dashboard_id}")

    if args.with_app:
        phase_app(genie_id, dashboard_id)
    else:
        print("\n  (App not deployed. Re-run with --with-app, or follow app/README section.)")


if __name__ == "__main__":
    main()
