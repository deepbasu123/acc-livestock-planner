"""Create the Lakebase schema/tables and seed them on first startup.

Runs as the app's service principal, which owns the `acc` schema (it creates
it here, so it becomes the owner - the deploy-first workflow). Everything is
idempotent: DDL uses IF NOT EXISTS and seeding only fills a table that is
currently empty, so restarts and redeploys are safe.
"""
import json
import logging
import os

from sqlalchemy import text

from . import pg

log = logging.getLogger("acc.pg.bootstrap")

SCHEMA = pg.SCHEMA
SEED_DIR = os.path.join(os.path.dirname(__file__), "seed")

# id/name/active master lists (agents, vendors, payees, buyers, programs,
# weigh_points, origins) all share this shape.
_MASTER_COLS = ["id", "name", "active", "created_at", "updated_at"]
MASTER_TABLES = ["agents", "vendors", "payees", "buyers", "programs", "weigh_points", "origins"]

BOOKING_COLS = [
    "id", "property", "status", "week_number", "week_commencing", "head_count", "delivery_day",
    "agent_id", "vendor_id", "payee_id", "grid_text", "program", "price_per_kg", "price_variation",
    "weigh_point_id", "origin_id", "buyer_id", "buyer_payee_details", "notes",
    "created_by", "created_by_email", "created_at", "modified_by", "modified_by_email",
    "updated_at", "deleted_at",
]
HISTORY_COLS = [
    "id", "booking_id", "action", "changed_by", "changed_by_email", "changed_at",
    "old_data", "new_data",
]
FEEDLOT_COLS = ["property", "feedlot_name", "suburb", "state", "total_capacity_head", "target_utilization_pct"]

# table -> ordered column list, used for seeding.
TABLE_COLS = {
    "feedlots": FEEDLOT_COLS,
    **{t: _MASTER_COLS for t in MASTER_TABLES},
    "cattle_bookings": BOOKING_COLS,
    "booking_history": HISTORY_COLS,
}
# Seed load order respects nothing (no FK constraints), but keep it readable.
SEED_ORDER = ["feedlots", *MASTER_TABLES, "cattle_bookings", "booking_history"]


def _ddl() -> list[str]:
    stmts = [f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"]
    for t in MASTER_TABLES:
        stmts.append(f"""CREATE TABLE IF NOT EXISTS {SCHEMA}.{t} (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )""")
    stmts.append(f"""CREATE TABLE IF NOT EXISTS {SCHEMA}.feedlots (
        property TEXT PRIMARY KEY,
        feedlot_name TEXT NOT NULL,
        suburb TEXT,
        state TEXT,
        total_capacity_head INTEGER,
        target_utilization_pct DOUBLE PRECISION
    )""")
    stmts.append(f"""CREATE TABLE IF NOT EXISTS {SCHEMA}.cattle_bookings (
        id TEXT PRIMARY KEY,
        property TEXT NOT NULL,
        status TEXT NOT NULL,
        week_number TEXT,
        week_commencing DATE,
        head_count INTEGER,
        delivery_day TEXT,
        agent_id TEXT,
        vendor_id TEXT,
        payee_id TEXT,
        grid_text TEXT,
        program TEXT,
        price_per_kg TEXT,
        price_variation TEXT,
        weigh_point_id TEXT,
        origin_id TEXT,
        buyer_id TEXT,
        buyer_payee_details TEXT,
        notes TEXT,
        created_by TEXT,
        created_by_email TEXT,
        created_at TIMESTAMP,
        modified_by TEXT,
        modified_by_email TEXT,
        updated_at TIMESTAMP,
        deleted_at TIMESTAMP
    )""")
    stmts.append(f"""CREATE TABLE IF NOT EXISTS {SCHEMA}.booking_history (
        id TEXT PRIMARY KEY,
        booking_id TEXT,
        action TEXT,
        changed_by TEXT,
        changed_by_email TEXT,
        changed_at TIMESTAMP,
        old_data TEXT,
        new_data TEXT
    )""")
    # Indexes that matter for the hot paths (list, filters, detail, history).
    stmts += [
        f"CREATE INDEX IF NOT EXISTS ix_bookings_deleted ON {SCHEMA}.cattle_bookings (deleted_at)",
        f"CREATE INDEX IF NOT EXISTS ix_bookings_updated ON {SCHEMA}.cattle_bookings (updated_at DESC)",
        f"CREATE INDEX IF NOT EXISTS ix_bookings_vendor ON {SCHEMA}.cattle_bookings (vendor_id)",
        f"CREATE INDEX IF NOT EXISTS ix_bookings_agent ON {SCHEMA}.cattle_bookings (agent_id)",
        f"CREATE INDEX IF NOT EXISTS ix_bookings_week ON {SCHEMA}.cattle_bookings (week_commencing)",
        f"CREATE INDEX IF NOT EXISTS ix_history_booking ON {SCHEMA}.booking_history (booking_id)",
    ]
    stmts += _view_ddl()
    return stmts


def _view_ddl() -> list[str]:
    """Gold views, Postgres port of sql/02_gold_views.sql. Same names/columns so
    the analytics routes read them exactly as they read the Delta gold layer.
    The Databricks SQL `TRY_CAST(regexp_extract(...))` becomes a POSIX
    `substring(... from '...')::double precision` (a non-matching pattern yields
    NULL, so a free-text price that doesn't parse stays NULL, as before)."""
    S = SCHEMA
    return [
        f"""CREATE OR REPLACE VIEW {S}.booking_expanded AS
        SELECT
          b.id, b.property, f.feedlot_name, f.total_capacity_head, b.status,
          b.week_number, b.week_commencing, b.head_count, b.delivery_day,
          b.agent_id, ag.name AS agent_name,
          b.vendor_id, v.name AS vendor_name,
          b.payee_id, p.name AS payee_name,
          b.grid_text, b.program, b.price_per_kg,
          CAST(substring(b.price_per_kg from '[0-9]+\\.?[0-9]*') AS DOUBLE PRECISION) AS price_per_kg_numeric,
          b.price_variation,
          b.weigh_point_id, wp.name AS weigh_point_name,
          b.origin_id, o.name AS origin_name,
          b.buyer_id, by2.name AS buyer_name,
          b.buyer_payee_details, b.notes,
          b.created_by, b.created_by_email, b.created_at,
          b.modified_by, b.modified_by_email, b.updated_at, b.deleted_at
        FROM {S}.cattle_bookings b
        LEFT JOIN {S}.feedlots f ON b.property = f.property
        LEFT JOIN {S}.agents ag ON b.agent_id = ag.id
        LEFT JOIN {S}.vendors v ON b.vendor_id = v.id
        LEFT JOIN {S}.payees p ON b.payee_id = p.id
        LEFT JOIN {S}.weigh_points wp ON b.weigh_point_id = wp.id
        LEFT JOIN {S}.origins o ON b.origin_id = o.id
        LEFT JOIN {S}.buyers by2 ON b.buyer_id = by2.id
        WHERE b.deleted_at IS NULL""",

        f"""CREATE OR REPLACE VIEW {S}.feedlot_weekly_bookings AS
        SELECT property, feedlot_name, total_capacity_head,
          week_commencing AS week_start,
          SUM(head_count) AS head_booked,
          COUNT(*) AS bookings_count
        FROM {S}.booking_expanded
        WHERE status <> 'Cancelled' AND week_commencing IS NOT NULL
        GROUP BY property, feedlot_name, total_capacity_head, week_commencing""",

        f"""CREATE OR REPLACE VIEW {S}.feedlot_capacity_weekly AS
        SELECT w.*,
          SUM(head_booked) OVER (PARTITION BY property ORDER BY week_start
              ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS head_on_feed_est,
          ROUND(100.0 * SUM(head_booked) OVER (PARTITION BY property ORDER BY week_start
              ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) / NULLIF(total_capacity_head, 0), 1) AS utilization_pct
        FROM {S}.feedlot_weekly_bookings w""",

        f"""CREATE OR REPLACE VIEW {S}.vendor_scorecard AS
        SELECT
          v.id AS vendor_id, v.name AS vendor_name, v.active,
          COUNT(b.id) AS total_bookings,
          SUM(CASE WHEN b.status = 'Cancelled' THEN 1 ELSE 0 END) AS cancelled_bookings,
          ROUND(100.0 * SUM(CASE WHEN b.status = 'Cancelled' THEN 1 ELSE 0 END) / NULLIF(COUNT(b.id), 0), 1) AS cancellation_rate_pct,
          SUM(CASE WHEN b.status <> 'Cancelled' THEN b.head_count ELSE 0 END) AS total_head_booked,
          ROUND(AVG(b.price_per_kg_numeric)::numeric, 2) AS avg_price_per_kg
        FROM {S}.vendors v
        LEFT JOIN {S}.booking_expanded b ON v.id = b.vendor_id
        GROUP BY v.id, v.name, v.active""",

        f"""CREATE OR REPLACE VIEW {S}.agent_performance AS
        SELECT
          ag.id AS agent_id, ag.name AS agent_name, ag.active,
          COUNT(b.id) AS total_bookings,
          SUM(CASE WHEN b.status <> 'Cancelled' THEN b.head_count ELSE 0 END) AS total_head_booked,
          COUNT(DISTINCT b.vendor_id) AS distinct_vendors
        FROM {S}.agents ag
        LEFT JOIN {S}.booking_expanded b ON ag.id = b.agent_id
        GROUP BY ag.id, ag.name, ag.active""",

        f"""CREATE OR REPLACE VIEW {S}.price_trend_weekly AS
        SELECT property, feedlot_name, week_commencing AS week_start,
          ROUND(AVG(price_per_kg_numeric)::numeric, 2) AS avg_price_per_kg
        FROM {S}.booking_expanded
        WHERE price_per_kg_numeric IS NOT NULL AND week_commencing IS NOT NULL
        GROUP BY property, feedlot_name, week_commencing""",
    ]


def _seed_file(table: str) -> str:
    return os.path.join(SEED_DIR, f"{table}.jsonl")


def _load_seed(table: str) -> list[dict]:
    path = _seed_file(table)
    if not os.path.isfile(path):
        return []
    rows = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def bootstrap() -> None:
    """Create schema, tables and indexes. Idempotent."""
    with pg.engine().begin() as conn:
        for stmt in _ddl():
            conn.execute(text(stmt))
    log.info("Lakebase schema '%s' ready", SCHEMA)


def seed_if_empty() -> None:
    """Fill each empty table from its shipped seed file. No-op once populated."""
    for table in SEED_ORDER:
        cols = TABLE_COLS[table]
        with pg.engine().begin() as conn:
            n = conn.execute(text(f"SELECT COUNT(*) AS n FROM {SCHEMA}.{table}")).scalar_one()
            if n and int(n) > 0:
                continue
            rows = _load_seed(table)
            if not rows:
                log.warning("no seed data for %s (skipping)", table)
                continue
            norm = [{c: r.get(c) for c in cols} for r in rows]
            collist = ", ".join(cols)
            placeholders = ", ".join(f":{c}" for c in cols)
            conn.execute(text(f"INSERT INTO {SCHEMA}.{table} ({collist}) VALUES ({placeholders})"), norm)
            log.info("seeded %s with %d rows", table, len(norm))


def init() -> None:
    bootstrap()
    seed_if_empty()
