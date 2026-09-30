#!/usr/bin/env python3
"""Reusable Databricks SQL Statements API runner for the ACC Livestock Planner demo.

Usage:
    python3 dbsql.py "SELECT 1"
    python3 dbsql.py --file path/to/file.sql      # runs statements split on ';' lines
    echo "SELECT 1" | python3 dbsql.py -

Configure via config.sh / env: ACC_PROFILE, ACC_HOST, ACC_WAREHOUSE, ACC_CATALOG.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

PROFILE = os.environ.get("ACC_PROFILE", "DEFAULT")
HOST = os.environ.get("ACC_HOST", "")
WAREHOUSE_ID = os.environ.get("ACC_WAREHOUSE", "")
CATALOG = os.environ.get("ACC_CATALOG", "")


def token():
    out = subprocess.check_output(
        ["databricks", "auth", "token", "--profile", PROFILE], text=True
    )
    return json.loads(out)["access_token"]


_TOKEN = None


def _hdr():
    global _TOKEN
    if _TOKEN is None:
        _TOKEN = token()
    return {"Authorization": f"Bearer {_TOKEN}", "Content-Type": "application/json"}


def _api(method, path, body=None):
    url = f"{HOST}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_hdr(), method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}") from None


def run(sql, catalog=CATALOG, schema=None, quiet=False):
    """Run one SQL statement, polling to completion. Returns result dict or raises."""
    body = {
        "warehouse_id": WAREHOUSE_ID,
        "statement": sql,
        "wait_timeout": "50s",
        "on_wait_timeout": "CONTINUE",
        "format": "JSON_ARRAY",
        "disposition": "INLINE",
    }
    if catalog:
        body["catalog"] = catalog
    if schema:
        body["schema"] = schema
    resp = _api("POST", "/api/2.0/sql/statements", body)
    sid = resp["statement_id"]
    state = resp["status"]["state"]
    while state in ("PENDING", "RUNNING"):
        time.sleep(2)
        resp = _api("GET", f"/api/2.0/sql/statements/{sid}")
        state = resp["status"]["state"]
    if state != "SUCCEEDED":
        err = resp["status"].get("error", {})
        raise RuntimeError(f"SQL FAILED: {err.get('message', state)}\n--SQL--\n{sql[:500]}")
    if not quiet:
        n = resp.get("result", {}).get("row_count", 0)
        print(f"  ok ({n} rows) :: {sql.strip().splitlines()[0][:80]}")
    return resp


def rows(sql, catalog=CATALOG, schema=None):
    r = run(sql, catalog, schema, quiet=True)
    return r.get("result", {}).get("data_array", []) or []


def run_script(text, catalog=CATALOG, schema=None):
    """Split a multi-statement script on ';' that ends a line, run each."""
    stmts, buf = [], []
    for line in text.splitlines():
        if line.strip().startswith("--"):
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip().rstrip(";").strip()
            if stmt:
                stmts.append(stmt)
            buf = []
    tail = "\n".join(buf).strip().rstrip(";").strip()
    if tail:
        stmts.append(tail)
    for s in stmts:
        run(s, catalog, schema)
    return len(stmts)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--file":
        with open(sys.argv[2]) as f:
            n = run_script(f.read())
        print(f"ran {n} statements")
    elif len(sys.argv) == 2 and sys.argv[1] == "-":
        n = run_script(sys.stdin.read())
        print(f"ran {n} statements")
    elif len(sys.argv) >= 2:
        r = run(" ".join(sys.argv[1:]))
        data = r.get("result", {}).get("data_array", [])
        cols = [c["name"] for c in r.get("manifest", {}).get("schema", {}).get("columns", [])]
        if cols:
            print("\t".join(cols))
        for row in data[:100]:
            print("\t".join("" if v is None else str(v) for v in row))
    else:
        print(__doc__)
