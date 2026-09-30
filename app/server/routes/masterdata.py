"""Master data CRUD: agents, vendors, payees, programs, weigh_points, origins, buyers.

Mirrors the reference app's admin screen exactly - each list has id/name/active,
only active rows should populate booking-form dropdowns, and any row can be
renamed, (de)activated or deleted (historical bookings keep their FK reference
even if the master row is later deactivated or removed).

Backed by Lakebase (Postgres); parameterised queries throughout.
"""
import datetime as dt
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import pg

router = APIRouter()

# All master lists live in the app-owned Postgres schema (search_path=acc).
LABELS = {
    "agents": "Agents", "vendors": "Vendor Properties", "payees": "Payees", "buyers": "Buyers",
    "programs": "Programs", "weigh_points": "Weigh Points", "origins": "Origins",
}


def _table(name: str) -> str:
    if name not in LABELS:
        raise HTTPException(404, f"Unknown master table '{name}'")
    return name


@router.get("/masterdata")
def list_tables():
    return {"tables": [{"id": t, "label": LABELS[t]} for t in LABELS]}


@router.get("/masterdata/{table}")
def list_rows(table: str, active_only: bool = False):
    t = _table(table)
    where = "WHERE active = true" if active_only else ""
    rows = pg.query(f"SELECT id, name, active, created_at, updated_at FROM {t} {where} ORDER BY name")
    return {"table": table, "label": LABELS[table], "rows": rows}


class CreateRow(BaseModel):
    name: str


@router.post("/masterdata/{table}")
def create_row(table: str, req: CreateRow):
    t = _table(table)
    if not req.name.strip():
        raise HTTPException(400, "name is required")
    row_id = str(uuid.uuid4())
    now = dt.datetime.utcnow()
    pg.execute(
        f"INSERT INTO {t} (id, name, active, created_at, updated_at) "
        f"VALUES (:id, :name, true, :now, :now)",
        {"id": row_id, "name": req.name.strip(), "now": now},
    )
    return {"id": row_id, "name": req.name.strip(), "active": True}


class UpdateRow(BaseModel):
    name: str | None = None
    active: bool | None = None


@router.patch("/masterdata/{table}/{row_id}")
def update_row(table: str, row_id: str, req: UpdateRow):
    t = _table(table)
    sets, params = [], {"id": row_id, "now": dt.datetime.utcnow()}
    if req.name is not None:
        sets.append("name = :name")
        params["name"] = req.name.strip()
    if req.active is not None:
        sets.append("active = :active")
        params["active"] = req.active
    if not sets:
        raise HTTPException(400, "nothing to update")
    sets.append("updated_at = :now")
    pg.execute(f"UPDATE {t} SET {', '.join(sets)} WHERE id = :id", params)
    return {"ok": True}


@router.delete("/masterdata/{table}/{row_id}")
def delete_row(table: str, row_id: str):
    t = _table(table)
    pg.execute(f"DELETE FROM {t} WHERE id = :id", {"id": row_id})
    return {"ok": True}
