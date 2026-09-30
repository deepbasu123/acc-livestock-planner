"""Feedlot capacity forecast + AI capacity optimisation strategy.

Derived entirely from cattle_bookings (there is no separate receival/turnoff
system in the reference app) - an estimate, clearly labelled as such. Reads the
Lakebase gold views (see server/pg_bootstrap.py)."""
from fastapi import APIRouter
from pydantic import BaseModel

from .. import pg
from ..llm import chat

router = APIRouter()


def _band(util, target):
    if util is None:
        return "PENDING"
    if util > target + 12:
        return "ACTION"
    if util > target + 4:
        return "WATCH"
    if util < target - 25:
        return "UNDER"
    return "OPTIMAL"


def _action(band, feedlot_name):
    return {
        "ACTION": f"Over target - hold new {feedlot_name} bookings or redirect to a feedlot with headroom.",
        "WATCH": f"Approaching target - monitor {feedlot_name} intake over the next 2-3 weeks.",
        "OPTIMAL": f"Running near target - {feedlot_name} has some room for new bookings.",
        "UNDER": f"Well under target - {feedlot_name} has plenty of headroom for new bookings.",
        "PENDING": "Not enough booking data yet for this feedlot.",
    }[band]


@router.get("/capacity")
def capacity(persona: str = "exec"):
    weekly = pg.query("""SELECT property, feedlot_name, week_start, head_booked, head_on_feed_est,
        utilization_pct, total_capacity_head FROM feedlot_capacity_weekly ORDER BY week_start""")
    feedlots = pg.query("SELECT property, feedlot_name, total_capacity_head, target_utilization_pct FROM feedlots ORDER BY property")
    price = pg.query("SELECT property, feedlot_name, week_start, avg_price_per_kg FROM price_trend_weekly ORDER BY week_start")

    # Use each feedlot's own latest week. A global max week misses any feedlot
    # that has no bookings in that exact week (Opal Ck often trails the others).
    latest_by_feedlot = {}
    for w in weekly:
        p = w["property"]
        prev = latest_by_feedlot.get(p)
        if prev is None or str(w["week_start"] or "") > str(prev.get("week_start") or ""):
            latest_by_feedlot[p] = w

    forecast = []
    for f in feedlots:
        lw = latest_by_feedlot.get(f["property"], {})
        util = lw.get("utilization_pct")
        target = float(f["target_utilization_pct"])
        band = _band(float(util) if util is not None else None, target)
        forecast.append({
            "property": f["property"], "feedlot_name": f["feedlot_name"],
            "current_utilization_pct": float(util) if util is not None else None,
            "target_utilization_pct": target,
            "head_on_feed_est": lw.get("head_on_feed_est"), "total_capacity_head": f["total_capacity_head"],
            "band": band, "recommended_action": _action(band, f["feedlot_name"]),
        })

    upcoming = pg.query("""SELECT SUM(head_count) AS head FROM booking_expanded
        WHERE status IN ('Draft','Confirmed') AND week_commencing > CURRENT_DATE""")
    upcoming_head = int(upcoming[0]["head"] or 0) if upcoming and upcoming[0]["head"] is not None else 0

    price_change_pct = None
    if len(price) > 8:
        by_week = {}
        for p in price:
            by_week.setdefault(str(p["week_start"]), []).append(float(p["avg_price_per_kg"] or 0))
        weeks_sorted = sorted(by_week.keys())
        first = sum(by_week[weeks_sorted[0]]) / len(by_week[weeks_sorted[0]])
        last = sum(by_week[weeks_sorted[-1]]) / len(by_week[weeks_sorted[-1]])
        price_change_pct = round(100.0 * (last - first) / first, 1) if first else None

    kpi = {
        "peak_utilization_pct": max((f["current_utilization_pct"] for f in forecast if f["current_utilization_pct"] is not None), default=None),
        "feedlots_over_target": sum(1 for f in forecast if f["band"] in ("WATCH", "ACTION")),
        "upcoming_head": upcoming_head,
        "price_change_pct": price_change_pct,
    }
    return {"persona": persona, "kpi": kpi, "weekly": weekly, "price_trend": price, "forecast": forecast}


class InsightReq(BaseModel):
    persona: str = "exec"


@router.post("/capacity/ai-insight")
def ai_insight(req: InsightReq):
    forecast = pg.query("""
        SELECT f.feedlot_name, f.target_utilization_pct, w.utilization_pct AS current_util
        FROM feedlots f
        LEFT JOIN (
          SELECT property, utilization_pct,
                 ROW_NUMBER() OVER (PARTITION BY property ORDER BY week_start DESC) AS rn
          FROM feedlot_capacity_weekly
        ) w ON f.property = w.property AND w.rn = 1""")
    facts = "\n".join(
        f"- {r['feedlot_name']}: currently ~{r['current_util']}% utilised against a {r['target_utilization_pct']}% target"
        if r.get("current_util") is not None else
        f"- {r['feedlot_name']}: no utilisation estimate yet (target {r['target_utilization_pct']}%)"
        for r in forecast)
    msgs = [
        {"role": "system", "content": (
            "You are an operations planner for Australian Country Choice (ACC), a vertically integrated "
            "Australian beef company. Given each feedlot's current capacity utilisation vs its target (estimated "
            "from booked head count, not a full receival system), write a concise capacity optimisation strategy "
            "for the procurement team. Use Australian English. Be specific and quantitative. Structure: a one-line "
            "headline on the network-wide capacity position, then 3-4 bullet recommendations (which feedlot(s) to "
            "hold/redirect bookings from or to, timing), then a one-line bottom line. Under 180 words.")},
        {"role": "user", "content": f"Current feedlot capacity position:\n\n{facts}"},
    ]
    try:
        insight = chat(msgs, max_tokens=600)
    except Exception as e:
        insight = f"(AI insight unavailable: {e})"
    return {"insight": insight}
