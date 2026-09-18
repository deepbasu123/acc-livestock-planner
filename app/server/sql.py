"""SQL execution against the Databricks SQL warehouse (dual-mode)."""
import time
from .config import get_client, WAREHOUSE_ID, CATALOG


def run(statement: str, params=None):
    """Execute SQL, return list[dict]. Polls to completion."""
    w = get_client()
    kwargs = dict(warehouse_id=WAREHOUSE_ID, statement=statement,
                  catalog=CATALOG, wait_timeout="30s")
    resp = w.statement_execution.execute_statement(**kwargs)
    sid = resp.statement_id
    state = resp.status.state.value if resp.status and resp.status.state else "FAILED"
    while state in ("PENDING", "RUNNING"):
        time.sleep(1)
        resp = w.statement_execution.get_statement(sid)
        state = resp.status.state.value if resp.status and resp.status.state else "FAILED"
    if state != "SUCCEEDED":
        msg = resp.status.error.message if (resp.status and resp.status.error) else state
        raise RuntimeError(f"SQL failed: {msg}")
    if not resp.manifest or not resp.manifest.schema:
        return []
    cols = [c.name for c in resp.manifest.schema.columns]
    out = []
    data = resp.result.data_array if (resp.result and resp.result.data_array) else []
    for row in data:
        out.append({c: v for c, v in zip(cols, row)})
    return out


def one(statement: str):
    rows = run(statement)
    return rows[0] if rows else {}
