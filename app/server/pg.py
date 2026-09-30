"""Lakebase Postgres access for the ACC Livestock Planner.

This is the operational data path. Bookings, master data and the audit log
live in Lakebase (managed Postgres), so every read and write is a low-latency
Postgres round-trip instead of a SQL-warehouse statement. Analytics (Genie /
dashboard) read the same data through Unity Catalog; see server/sql.py.

Auth model (Databricks Apps): the app's service principal mints a short-lived
(1 hour) OAuth database credential via the SDK and uses it as the Postgres
password. We refresh it on a background thread and inject the current token on
every new pooled connection, so long-lived pools never present a stale token.
Connection env (PGHOST/PGUSER/PGDATABASE/LAKEBASE_ENDPOINT) is provided by the
app's `postgres` resource; locally it comes from config.sh.
"""
import logging
import os
import threading
import time
from functools import lru_cache

from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import QueuePool

from .config import get_client

log = logging.getLogger("acc.pg")

PGHOST = os.environ.get("PGHOST", "")
PGPORT = int(os.environ.get("PGPORT", "5432") or "5432")
PGDATABASE = os.environ.get("PGDATABASE", "databricks_postgres")
PGUSER = os.environ.get("PGUSER", "")
# Endpoint resource path the credential is minted for:
#   projects/{project}/branches/{branch}/endpoints/{endpoint}
LAKEBASE_ENDPOINT = os.environ.get("LAKEBASE_ENDPOINT", "")
# The app's service principal owns this schema (it CREATEs it on first startup).
SCHEMA = os.environ.get("ACC_PG_SCHEMA", "acc")

# Refresh well inside the 1-hour credential lifetime.
_REFRESH_EVERY_S = 30 * 60

_token = {"value": None}
_token_lock = threading.Lock()
_refresh_started = False


def _mint_token() -> str:
    """Mint a fresh 1-hour Postgres OAuth credential for the primary endpoint."""
    if not LAKEBASE_ENDPOINT:
        raise RuntimeError("LAKEBASE_ENDPOINT is not set; cannot mint a Lakebase credential")
    cred = get_client().postgres.generate_database_credential(endpoint=LAKEBASE_ENDPOINT)
    return cred.token


def _refresh_loop():
    while True:
        time.sleep(_REFRESH_EVERY_S)
        try:
            tok = _mint_token()
            with _token_lock:
                _token["value"] = tok
            log.info("Lakebase credential refreshed")
        except Exception as e:  # keep the loop alive; retry sooner on failure
            log.warning("Lakebase credential refresh failed: %s", e)
            time.sleep(60)


@lru_cache(maxsize=1)
def engine():
    """Build the pooled engine once. Token is injected per new connection."""
    global _refresh_started
    with _token_lock:
        _token["value"] = _mint_token()

    url = f"postgresql+psycopg://{PGUSER}@{PGHOST}:{PGPORT}/{PGDATABASE}"
    eng = create_engine(
        url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,     # revalidate after scale-to-zero wake-ups
        pool_recycle=3600,      # never keep a connection past the token lifetime
        connect_args={
            "sslmode": "require",
            # resolve bare table names against the app-owned schema
            "options": f"-csearch_path={SCHEMA},public",
        },
    )

    @event.listens_for(eng, "do_connect")
    def _inject_token(dialect, conn_rec, cargs, cparams):
        with _token_lock:
            cparams["password"] = _token["value"]

    if not _refresh_started:
        threading.Thread(target=_refresh_loop, daemon=True).start()
        _refresh_started = True

    return eng


def query(sql: str, params: dict | None = None) -> list[dict]:
    """Run a SELECT, return list[dict] with native Python types."""
    with engine().connect() as conn:
        result = conn.execute(text(sql), params or {})
        return [dict(row._mapping) for row in result]


def one(sql: str, params: dict | None = None) -> dict:
    rows = query(sql, params)
    return rows[0] if rows else {}


def execute(sql: str, params: dict | None = None) -> None:
    """Run a write statement in its own transaction."""
    with engine().begin() as conn:
        conn.execute(text(sql), params or {})


def tx():
    """Transaction context manager for multi-statement atomic writes:

        with pg.tx() as conn:
            conn.execute(text(...), params)
            row = conn.execute(text(...), params).mappings().first()
    """
    return engine().begin()
