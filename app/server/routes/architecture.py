"""Live deployed-object counts for the Architecture tab."""
from fastapi import APIRouter
from ..sql import run, one
from ..config import CATALOG

router = APIRouter()
SCHEMAS = ["acc_feedlot", "acc_counterparty", "acc_reference", "acc_booking", "acc_audit", "acc_gold"]
PREFIX_LIST = "','".join(SCHEMAS)


@router.get("/architecture/stats")
def stats():
    try:
        by_schema = run(f"""
            SELECT table_schema, COUNT(*) AS n FROM {CATALOG}.information_schema.tables
            WHERE table_schema IN ('{PREFIX_LIST}') GROUP BY table_schema ORDER BY table_schema""")
        masks = one(f"""
            SELECT COUNT(*) AS n FROM {CATALOG}.information_schema.column_masks
            WHERE table_schema IN ('{PREFIX_LIST}')""")
        tags = one(f"""
            SELECT COUNT(DISTINCT schema_name || '.' || table_name || '.' || column_name) AS n
            FROM {CATALOG}.information_schema.column_tags WHERE schema_name IN ('{PREFIX_LIST}')""")
        rows = one(f"""
            SELECT
              (SELECT COUNT(*) FROM {CATALOG}.acc_booking.cattle_bookings WHERE deleted_at IS NULL) AS bookings,
              (SELECT COUNT(*) FROM {CATALOG}.acc_counterparty.vendors) AS vendors,
              (SELECT COUNT(*) FROM {CATALOG}.acc_audit.booking_history) AS history_events,
              (SELECT COUNT(*) FROM {CATALOG}.acc_counterparty.agents) AS agents""")
        total_tables = sum(int(r["n"]) for r in by_schema)
        gold_views = next((int(r["n"]) for r in by_schema if r["table_schema"] == "acc_gold"), 0)
        return {"ok": True, "catalog": CATALOG, "by_schema": by_schema, "total_tables": total_tables,
                "gold_views": gold_views, "masks_applied": int(masks.get("n", 0)),
                "tagged_columns": int(tags.get("n", 0)), "row_counts": rows}
    except Exception as e:
        return {"ok": False, "error": str(e), "catalog": CATALOG}
