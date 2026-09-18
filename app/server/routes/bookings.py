"""Cattle booking CRUD - create/update/soft-delete/duplicate, each writing an
append-only booking_history row, exactly reproducing the reference app's
src/lib/bookings.ts query shapes (see docs/SPEC.md sec 3.4)."""
import datetime as dt
import json
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..sql import run, one
from ..config import CATALOG

router = APIRouter()
G = f"{CATALOG}.acc_gold"
BK = f"{CATALOG}.acc_booking"
AUD = f"{CATALOG}.acc_audit"
CP = f"{CATALOG}.acc_counterparty"
REF = f"{CATALOG}.acc_reference"
FL = f"{CATALOG}.acc_feedlot"

PROPERTIES = ["BPFL", "Opal Ck", "BVFL"]
STATUSES = ["Draft", "Confirmed", "Cancelled"]
APP_USER = ("ACC Livestock Planner", "app@accbeef.net.au")

FIELDS = ["property", "status", "week_number", "week_commencing", "head_count", "delivery_day",
          "agent_id", "vendor_id", "payee_id", "grid_text", "program", "price_per_kg", "price_variation",
          "weigh_point_id", "origin_id", "buyer_id", "buyer_payee_details", "notes"]


def _q(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def _now():
    return dt.datetime.utcnow().isoformat()


def _record_history(booking_id, action, changed_by, changed_by_email, old_data, new_data):
    run(f"""INSERT INTO {AUD}.booking_history (id, booking_id, action, changed_by, changed_by_email, changed_at, old_data, new_data)
        VALUES ({_q(str(uuid.uuid4()))}, {_q(booking_id)}, {_q(action)}, {_q(changed_by)}, {_q(changed_by_email)},
                {_q(_now())}, {_q(json.dumps(old_data) if old_data is not None else None)},
                {_q(json.dumps(new_data, default=str) if new_data is not None else None)})""")


PRICING_FIELDS = ("price_per_kg", "price_per_kg_numeric", "price_variation", "buyer_payee_details")


def _mask_pricing(row: dict, commercial: bool) -> dict:
    if commercial:
        return row
    r = dict(row)
    for f in PRICING_FIELDS:
        r[f] = None
    return r


@router.get("/bookings")
def list_bookings(persona: str = "exec"):
    """All non-deleted bookings, expanded, sorted most-recently-updated first
    (the reference app filters/searches this client-side). Pricing fields are
    masked server-side (not just hidden client-side) when the persona lacks
    commercial visibility, matching the Unity Catalog ABAC policy."""
    rows = run(f"""SELECT * FROM {G}.booking_expanded ORDER BY updated_at DESC NULLS LAST, created_at DESC LIMIT 5000""")
    commercial = persona in ("exec", "procurement")
    rows = [_mask_pricing(r, commercial) for r in rows]
    return {"persona": persona, "commercial_visible": commercial, "bookings": rows}


@router.get("/bookings/lookups")
def lookups():
    return {
        "properties": PROPERTIES,
        "statuses": STATUSES,
        "delivery_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "agents": run(f"SELECT id, name FROM {CP}.agents WHERE active = true ORDER BY name"),
        "vendors": run(f"SELECT id, name FROM {CP}.vendors WHERE active = true ORDER BY name"),
        "payees": run(f"SELECT id, name FROM {CP}.payees WHERE active = true ORDER BY name"),
        "programs": run(f"SELECT id, name FROM {REF}.programs WHERE active = true ORDER BY name"),
        "weigh_points": run(f"SELECT id, name FROM {REF}.weigh_points WHERE active = true ORDER BY name"),
        "origins": run(f"SELECT id, name FROM {REF}.origins WHERE active = true ORDER BY name"),
        "buyers": run(f"SELECT id, name FROM {CP}.buyers WHERE active = true ORDER BY name"),
    }


@router.get("/bookings/{booking_id}")
def get_booking(booking_id: str, persona: str = "exec"):
    b = one(f"SELECT * FROM {G}.booking_expanded WHERE id = {_q(booking_id)}")
    if not b:
        raise HTTPException(404, "Booking not found")
    return b


@router.get("/bookings/{booking_id}/history")
def get_history(booking_id: str):
    rows = run(f"""SELECT id, booking_id, action, changed_by, changed_by_email, changed_at, old_data, new_data
        FROM {AUD}.booking_history WHERE booking_id = {_q(booking_id)} ORDER BY changed_at DESC""")
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
    if not b.week_number and not b.week_commencing:
        raise HTTPException(400, "Week is required")
    if not b.head_count or b.head_count <= 0:
        raise HTTPException(400, "Head Count must be greater than 0")


@router.post("/bookings")
def create_booking(req: BookingIn):
    _validate(req)
    booking_id = str(uuid.uuid4())
    now = _now()
    data = req.model_dump()
    cols = ["id", *FIELDS, "created_by", "created_by_email", "created_at", "updated_at"]
    vals = [_q(booking_id), *[_q(data[f]) for f in FIELDS], _q(APP_USER[0]), _q(APP_USER[1]), _q(now), _q(now)]
    run(f"INSERT INTO {BK}.cattle_bookings ({', '.join(cols)}) VALUES ({', '.join(vals)})")
    new_row = one(f"SELECT * FROM {G}.booking_expanded WHERE id = {_q(booking_id)}")
    _record_history(booking_id, "create", *APP_USER, None, new_row)
    return new_row


@router.patch("/bookings/{booking_id}")
def update_booking(booking_id: str, req: BookingIn):
    _validate(req)
    previous = one(f"SELECT * FROM {G}.booking_expanded WHERE id = {_q(booking_id)}")
    if not previous:
        raise HTTPException(404, "Booking not found")
    data = req.model_dump()
    sets = [f"{f} = {_q(data[f])}" for f in FIELDS]
    sets += [f"modified_by = {_q(APP_USER[0])}", f"modified_by_email = {_q(APP_USER[1])}", f"updated_at = {_q(_now())}"]
    run(f"UPDATE {BK}.cattle_bookings SET {', '.join(sets)} WHERE id = {_q(booking_id)}")
    new_row = one(f"SELECT * FROM {G}.booking_expanded WHERE id = {_q(booking_id)}")
    _record_history(booking_id, "update", *APP_USER, previous, new_row)
    return new_row


@router.delete("/bookings/{booking_id}")
def delete_booking(booking_id: str):
    """Soft delete only - sets deleted_at, never removes the row."""
    previous = one(f"SELECT * FROM {G}.booking_expanded WHERE id = {_q(booking_id)}")
    if not previous:
        raise HTTPException(404, "Booking not found")
    now = _now()
    run(f"UPDATE {BK}.cattle_bookings SET deleted_at = {_q(now)}, updated_at = {_q(now)} WHERE id = {_q(booking_id)}")
    _record_history(booking_id, "delete", *APP_USER, None, {"deleted_at": now})
    return {"ok": True}


@router.post("/bookings/{booking_id}/duplicate")
def duplicate_booking(booking_id: str):
    """Copies all business fields, resets status to Draft, strips audit/identity fields."""
    source = one(f"SELECT * FROM {G}.booking_expanded WHERE id = {_q(booking_id)}")
    if not source:
        raise HTTPException(404, "Booking not found")
    new_id = str(uuid.uuid4())
    now = _now()
    data = {f: source.get(f) for f in FIELDS}
    data["status"] = "Draft"
    cols = ["id", *FIELDS, "created_by", "created_by_email", "created_at", "updated_at"]
    vals = [_q(new_id), *[_q(data[f]) for f in FIELDS], _q(APP_USER[0]), _q(APP_USER[1]), _q(now), _q(now)]
    run(f"INSERT INTO {BK}.cattle_bookings ({', '.join(cols)}) VALUES ({', '.join(vals)})")
    new_row = one(f"SELECT * FROM {G}.booking_expanded WHERE id = {_q(new_id)}")
    _record_history(new_id, "duplicate", *APP_USER, {"duplicated_from": booking_id}, new_row)
    return new_row
