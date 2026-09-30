"""Governance: persona-driven commercial-pricing masking demonstration.

The backend reads unmasked base data and applies the persona policy in the app
(the app runs as its own service principal), so the persona toggle visibly
reproduces the governance outcome:
  exec        -> sees everything
  procurement -> sees pricing (price_per_kg, price_variation, buyer_payee_details)
  operations  -> sees booking/logistics fields; pricing is masked
Reads the Lakebase gold views (see server/pg_bootstrap.py)."""
from fastapi import APIRouter

from .. import pg

router = APIRouter()

POLICY = [
    ("Feedlot, status, head count, week", "logistics", ["exec", "procurement", "operations"]),
    ("Agent / vendor / payee / buyer names", "logistics", ["exec", "procurement", "operations"]),
    ("Price per Kg", "pricing", ["exec", "procurement"]),
    ("Price Variation", "pricing", ["exec", "procurement"]),
    ("Buyer Payee Details", "pricing", ["exec", "procurement"]),
]


def _vis(key, persona):
    for _, k, allowed in POLICY:
        if k == key:
            return persona in allowed
    return False


@router.get("/governance/policy")
def policy(persona: str = "exec"):
    return {"persona": persona, "rows": [
        {"field": label, "key": key, "visible": persona in allowed, "visible_to": allowed}
        for label, key, allowed in POLICY]}


@router.get("/governance/bookings-sample")
def bookings_sample(persona: str = "exec"):
    vis = _vis("pricing", persona)
    price = "price_per_kg" if vis else "'███ REDACTED'"
    var = "price_variation" if vis else "'███ REDACTED'"
    payee = "buyer_payee_details" if vis else "'███ REDACTED'"
    rows = pg.query(f"""SELECT id, property, vendor_name, buyer_name, head_count,
        {price} AS price_per_kg, {var} AS price_variation, {payee} AS buyer_payee_details, status
        FROM booking_expanded ORDER BY updated_at DESC NULLS LAST LIMIT 15""")
    return {"persona": persona, "pricing_visible": vis, "bookings": rows}


@router.get("/governance/vendor-scorecard")
def vendor_scorecard(persona: str = "exec"):
    vis = _vis("pricing", persona)
    price = "avg_price_per_kg" if vis else "NULL"
    rows = pg.query(f"""SELECT vendor_id, vendor_name, total_bookings, cancellation_rate_pct, total_head_booked,
        {price} AS avg_price_per_kg FROM vendor_scorecard WHERE total_bookings > 0
        ORDER BY total_head_booked DESC LIMIT 20""")
    return {"persona": persona, "pricing_visible": vis, "vendors": rows}


@router.get("/governance/agent-performance")
def agent_performance():
    rows = pg.query("""SELECT agent_id, agent_name, total_bookings, total_head_booked, distinct_vendors
        FROM agent_performance WHERE total_bookings > 0 ORDER BY total_head_booked DESC""")
    return {"agents": rows}
