"""Live deployed-object counts for the Architecture tab.

Now reports the Lakebase (Postgres) operational layer: the app-owned schema,
its tables + gold views, the governed commercial-pricing fields, and live row
counts - all read straight from Postgres."""
from fastapi import APIRouter

from .. import pg

router = APIRouter()

# Commercial-pricing fields the persona policy governs (see routes/governance.py).
GOVERNED_FIELDS = ["price_per_kg", "price_variation", "buyer_payee_details"]


@router.get("/architecture/stats")
def stats():
    try:
        schema = pg.SCHEMA
        tbls = pg.one(
            "SELECT COUNT(*) AS n FROM information_schema.tables "
            "WHERE table_schema = :s AND table_type = 'BASE TABLE'", {"s": schema})
        views = pg.one(
            "SELECT COUNT(*) AS n FROM information_schema.views WHERE table_schema = :s", {"s": schema})
        rows = pg.one("""SELECT
              (SELECT COUNT(*) FROM cattle_bookings WHERE deleted_at IS NULL) AS bookings,
              (SELECT COUNT(*) FROM vendors) AS vendors,
              (SELECT COUNT(*) FROM booking_history) AS history_events,
              (SELECT COUNT(*) FROM agents) AS agents""")
        n_tables = int(tbls.get("n", 0) or 0)
        n_views = int(views.get("n", 0) or 0)
        by_schema = [{"table_schema": schema, "n": n_tables + n_views}]
        return {"ok": True, "catalog": f"Lakebase / {schema}", "backend": "lakebase-postgres",
                "by_schema": by_schema, "total_tables": n_tables + n_views,
                "gold_views": n_views, "masks_applied": len(GOVERNED_FIELDS),
                "tagged_columns": len(GOVERNED_FIELDS), "row_counts": rows}
    except Exception as e:
        return {"ok": False, "error": str(e), "catalog": "Lakebase"}
