"""Cattle booking CRUD - create/update/soft-delete/duplicate, each writing an
append-only booking_history row in the same transaction, exactly reproducing
the reference app's src/lib/bookings.ts query shapes (see docs/SPEC.md sec 3.4).

Backed by Lakebase (Postgres): every read and write is a low-latency Postgres
round-trip. Queries are parameterised (no string interpolation), so the free
text booking fields can't break out of their values.
"""
import datetime as dt
import json
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text

from .. import pg

router = APIRouter()

PROPERTIES = ["BPFL", "Opal Ck", "BVFL"]
STATUSES = ["Draft", "Confirmed", "Cancelled"]
APP_USER = ("ACC Livestock Planner", "app@accbeef.net.au")

FIELDS = ["property", "status", "week_number", "week_commencing", "head_count", "delivery_day",
          "agent_id", "vendor_id", "payee_id", "grid_text", "program", "price_per_kg", "price_variation",
          "weigh_point_id", "origin_id", "buyer_id", "buyer_payee_details", "notes"]

PRICING_FIELDS = ("price_per_kg", "price_per_kg_numeric", "price_variation", "buyer_payee_details")


def _actor(request: Request) -> tuple[str, str]:
    """Real caller identity when running as a Databricks App: the platform's
    reverse proxy injects X-Forwarded-* headers with the signed-in user's
    identity (see https://docs.databricks.com/aws/en/dev-tools/databricks-apps/http-headers).
    Falls back to a generic app identity locally, where those headers aren't
    present (the reference app has no login - see docs/SPEC.md sec 5)."""
    email = request.headers.get("x-forwarded-email")
    name = request.headers.get("x-forwarded-preferred-username") or email
    if email:
        return (name or email, email)
    return APP_USER


def _now() -> dt.datetime:
    return dt.datetime.utcnow()


def _mask_pricing(row: dict, commercial: bool) -> dict:
    if commercial:
        return row
    r = dict(row)
    for f in PRICING_FIELDS:
        r[f] = None
    return r


def _history_stmt():
    return text("""INSERT INTO booking_history
        (id, booking_id, action, changed_by, changed_by_email, changed_at, old_data, new_data)
        VALUES (:id, :booking_id, :action, :changed_by, :changed_by_email, :changed_at, :old_data, :new_data)""")


def _history_params(booking_id, action, changed_by, changed_by_email, old_data, new_data):
    return {
        "id": str(uuid.uuid4()), "booking_id": booking_id, "action": action,
        "changed_by": changed_by, "changed_by_email": changed_by_email, "changed_at": _now(),
        # Postgres returns native Decimal/date/datetime in the expanded row, so
        # both snapshots need default=str (the Delta version got all-strings back
        # and could skip it on old_data).
        "old_data": json.dumps(old_data, default=str) if old_data is not None else None,
        "new_data": json.dumps(new_data, default=str) if new_data is not None else None,
    }


def _expanded(conn, booking_id):
    row = conn.execute(text("SELECT * FROM booking_expanded WHERE id = :id"), {"id": booking_id}).mappings().first()
    return dict(row) if row else None


@router.get("/bookings")
def list_bookings(persona: str = "exec"):
    """All non-deleted bookings, expanded, most-recently-updated first (the
    reference app filters/searches client-side). Pricing is masked server-side
    when the persona lacks commercial visibility, matching the persona policy."""
    rows = pg.query("""SELECT * FROM booking_expanded
        ORDER BY updated_at DESC NULLS LAST, created_at DESC LIMIT 5000""")
    commercial = persona in ("exec", "procurement")
    rows = [_mask_pricing(r, commercial) for r in rows]
    return {"persona": persona, "commercial_visible": commercial, "bookings": rows}


@router.get("/bookings/lookups")
def lookups():
    active = "SELECT id, name, active FROM {} ORDER BY name"
    return {
        "properties": PROPERTIES,
        "statuses": STATUSES,
        "delivery_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "agents": pg.query(active.format("agents")),
        "vendors": pg.query(active.format("vendors")),
        "payees": pg.query(active.format("payees")),
        "programs": pg.query(active.format("programs")),
        "weigh_points": pg.query(active.format("weigh_points")),
        "origins": pg.query(active.format("origins")),
        "buyers": pg.query(active.format("buyers")),
    }


@router.get("/bookings/{booking_id}")
def get_booking(booking_id: str):
    """Always returns unmasked pricing, deliberately - this feeds the edit form
    (see docs/SPEC.md sec 5). The persona-masking demo lives in the read-only
    Bookings list and Governance tab instead."""
    b = pg.one("SELECT * FROM booking_expanded WHERE id = :id", {"id": booking_id})
    if not b:
        raise HTTPException(404, "Booking not found")
    return b


@router.get("/bookings/{booking_id}/history")
def get_history(booking_id: str):
    rows = pg.query("""SELECT id, booking_id, action, changed_by, changed_by_email, changed_at, old_data, new_data
        FROM booking_history WHERE booking_id = :id ORDER BY changed_at DESC""", {"id": booking_id})
    return {"history": rows}


class BookingIn(BaseModel):
    property: str
    status: str = "Draft"
    week_number: str | None = None
    week_commencing: str | None = None
    head_count: int
    delivery_day: str | None = None
    agent_id: str | None = None
    vendor_id: str | None = None
    payee_id: str | None = None
    grid_text: str | None = None
    program: str | None = None
    price_per_kg: str | None = None
    price_variation: str | None = None
    weigh_point_id: str | None = None
    origin_id: str | None = None
    buyer_id: str | None = None
    buyer_payee_details: str | None = None
    notes: str | None = None


def _validate(b: BookingIn):
    if b.property not in PROPERTIES:
        raise HTTPException(400, "Destination Feedlot is required")
    if b.status not in STATUSES:
        raise HTTPException(400, f"status must be one of {STATUSES}")
    if not b.week_number and not b.week_commencing:
        raise HTTPException(400, "Week is required")
    if not b.head_count or b.head_count <= 0:
        raise HTTPException(400, "Head Count must be greater than 0")


@router.post("/bookings")
def create_booking(req: BookingIn, request: Request):
    _validate(req)
    actor = _actor(request)
    booking_id = str(uuid.uuid4())
    now = _now()
    data = req.model_dump()
    params = {f: data[f] for f in FIELDS}
    params.update(id=booking_id, created_by=actor[0], created_by_email=actor[1], created_at=now, updated_at=now)
    cols = ["id", *FIELDS, "created_by", "created_by_email", "created_at", "updated_at"]
    placeholders = ", ".join(f":{c}" for c in cols)
    with pg.tx() as conn:
        conn.execute(text(f"INSERT INTO cattle_bookings ({', '.join(cols)}) VALUES ({placeholders})"), params)
        new_row = _expanded(conn, booking_id)
        conn.execute(_history_stmt(), _history_params(booking_id, "create", *actor, None, new_row))
    return new_row


@router.patch("/bookings/{booking_id}")
def update_booking(booking_id: str, req: BookingIn, request: Request):
    _validate(req)
    actor = _actor(request)
    data = req.model_dump()
    with pg.tx() as conn:
        previous = _expanded(conn, booking_id)
        if not previous:
            raise HTTPException(404, "Booking not found")
        params = {f: data[f] for f in FIELDS}
        params.update(id=booking_id, modified_by=actor[0], modified_by_email=actor[1], updated_at=_now())
        sets = ", ".join(f"{f} = :{f}" for f in FIELDS)
        sets += ", modified_by = :modified_by, modified_by_email = :modified_by_email, updated_at = :updated_at"
        conn.execute(text(f"UPDATE cattle_bookings SET {sets} WHERE id = :id"), params)
        new_row = _expanded(conn, booking_id)
        conn.execute(_history_stmt(), _history_params(booking_id, "update", *actor, previous, new_row))
    return new_row


@router.delete("/bookings/{booking_id}")
def delete_booking(booking_id: str, request: Request):
    """Soft delete only - sets deleted_at, never removes the row."""
    actor = _actor(request)
    now = _now()
    with pg.tx() as conn:
        previous = _expanded(conn, booking_id)
        if not previous:
            raise HTTPException(404, "Booking not found")
        conn.execute(text("UPDATE cattle_bookings SET deleted_at = :now, updated_at = :now WHERE id = :id"),
                     {"now": now, "id": booking_id})
        deleted_row = dict(conn.execute(text("SELECT * FROM cattle_bookings WHERE id = :id"),
                                        {"id": booking_id}).mappings().first())
        conn.execute(_history_stmt(), _history_params(booking_id, "delete", *actor, previous, deleted_row))
    return {"ok": True}


@router.post("/bookings/{booking_id}/duplicate")
def duplicate_booking(booking_id: str, request: Request):
    """Copies all business fields, resets status to Draft, strips audit/identity fields."""
    actor = _actor(request)
    new_id = str(uuid.uuid4())
    now = _now()
    with pg.tx() as conn:
        source = _expanded(conn, booking_id)
        if not source:
            raise HTTPException(404, "Booking not found")
        params = {f: source.get(f) for f in FIELDS}
        params["status"] = "Draft"
        params.update(id=new_id, created_by=actor[0], created_by_email=actor[1], created_at=now, updated_at=now)
        cols = ["id", *FIELDS, "created_by", "created_by_email", "created_at", "updated_at"]
        placeholders = ", ".join(f":{c}" for c in cols)
        conn.execute(text(f"INSERT INTO cattle_bookings ({', '.join(cols)}) VALUES ({placeholders})"), params)
        new_row = _expanded(conn, new_id)
        conn.execute(_history_stmt(), _history_params(new_id, "duplicate", *actor, source, new_row))
    return new_row
