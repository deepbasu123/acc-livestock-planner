"""SQL execution against the Databricks SQL warehouse (dual-mode)."""
import time
from .config import get_client, WAREHOUSE_ID, CATALOG

# Databricks SQL Statement API JSON_ARRAY returns every cell as a string,
# including ints/bools/decimals. Official docs:
# https://docs.databricks.com/api/workspace/statementexecution/executestatement
#   "each non-null value is formatted as a string"
_INT_TYPES = {"BYTE", "SHORT", "INT", "LONG"}
_FLOAT_TYPES = {"FLOAT", "DOUBLE", "DECIMAL"}


def _type_name(col) -> str:
    tn = getattr(col, "type_name", None)
    if tn is None:
        return "STRING"
    return str(getattr(tn, "value", tn)).upper()


def _coerce(value, type_name: str):
    if value is None:
        return None
    if type_name in _INT_TYPES:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return value
    if type_name in _FLOAT_TYPES:
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    if type_name == "BOOLEAN":
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in ("true", "1", "t", "yes"):
            return True
        if s in ("false", "0", "f", "no"):
            return False
        return value
    return value


def _collect_rows(w, sid, first_resp):
    """INLINE JSON_ARRAY can span chunks; walk next_chunk_index until done."""
    result = first_resp.result
    rows = list(result.data_array) if (result and result.data_array) else []
    next_idx = result.next_chunk_index if result else None
    while next_idx is not None:
        chunk = w.statement_execution.get_statement_result_chunk_n(sid, next_idx)
        if chunk and chunk.data_array:
            rows.extend(chunk.data_array)
        next_idx = chunk.next_chunk_index if chunk else None
    return rows


def run(statement: str, params=None):
    """Execute SQL, return list[dict] with native Python types. Polls to completion."""
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
    cols = list(resp.manifest.schema.columns or [])
    names = [c.name for c in cols]
    types = [_type_name(c) for c in cols]
    out = []
    for row in _collect_rows(w, sid, resp):
        out.append({n: _coerce(v, t) for n, v, t in zip(names, row, types)})
    return out


def one(statement: str):
    rows = run(statement)
    return rows[0] if rows else {}
