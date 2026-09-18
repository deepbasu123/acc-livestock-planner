"""Feedlot capacity forecast + AI capacity optimisation strategy.

Derived entirely from cattle_bookings (there is no separate receival/turnoff
system in the reference app) - an estimate, clearly labelled as such."""
from fastapi import APIRouter
from pydantic import BaseModel
from ..sql import run
from ..llm import chat
from ..config import CATALOG

router = APIRouter()
G = f"{CATALOG}.acc_gold"
FL = f"{CATALOG}.acc_feedlot"


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
    weekly = run(f"""SELECT property, feedlot_name, week_start, head_booked, head_on_feed_est,
        utilization_pct, total_capacity_head FROM {G}.feedlot_capacity_weekly ORDER BY week_start""")
    feedlots = run(f"SELECT property, feedlot_name, total_capacity_head, target_utilization_pct FROM {FL}.feedlots ORDER BY property")
    price = run(f"SELECT property, feedlot_name, week_start, avg_price_per_kg FROM {G}.price_trend_weekly ORDER BY week_start")

    latest_week = max((w["week_start"] for w in weekly), default=None)
    latest_by_feedlot = {w["property"]: w for w in weekly if w["week_start"] == latest_week}

    forecast = []
    for f in feedlots:
        lw = latest_by_feedlot.get(f["property"], {})
        util = lw.get("utilization_pct")
        target = float(f["target_utilization_pct"])
        band = _band(float(util) if util is not None else None, target)
        forecast.append({
            "property": f["property"], "feedlot_name": f["feedlot_name"],
            "current_utilization_pct": util, "target_utilization_pct": target,
            "head_on_feed_est": lw.get("head_on_feed_est"), "total_capacity_head": f["total_capacity_head"],
            "band": band, "recommended_action": _action(band, f["feedlot_name"]),
        })

    upcoming = run(f"""SELECT SUM(head_count) AS head FROM {G}.booking_expanded
        WHERE status IN ('Draft','Confirmed') AND week_commencing > CURRENT_DATE()""")
    upcoming_head = int(upcoming[0]["head"] or 0) if upcoming else 0

    price_change_pct = None
    if len(price) > 8:
        by_week = {}
        for p in price:
            by_week.setdefault(p["week_start"], []).append(float(p["avg_price_per_kg"] or 0))
        weeks_sorted = sorted(by_week.keys())
        first = sum(by_week[weeks_sorted[0]]) / len(by_week[weeks_sorted[0]])
        last = sum(by_week[weeks_sorted[-1]]) / len(by_week[weeks_sorted[-1]])
        price_change_pct = round(100.0 * (last - first) / first, 1) if first else None

    kpi = {
        "peak_utilization_pct": max((float(f["current_utilization_pct"]) for f in forecast if f["current_utilization_pct"] is not None), default=None),
        "feedlots_over_target": sum(1 for f in forecast if f["band"] in ("WATCH", "ACTION")),
        "upcoming_head": upcoming_head,
        "price_change_pct": price_change_pct,
    }
    return {"persona": persona, "kpi": kpi, "weekly": weekly, "price_trend": price, "forecast": forecast}


class InsightReq(BaseModel):
    persona: str = "exec"


@router.post("/capacity/ai-insight")
def ai_insight(req: InsightReq):
    forecast = run(f"""
        SELECT f.feedlot_name, f.target_utilization_pct,
               MAX(CASE WHEN w.week_start = (SELECT MAX(week_start) FROM {G}.feedlot_capacity_weekly) THEN w.utilization_pct END) AS current_util
        FROM {FL}.feedlots f LEFT JOIN {G}.feedlot_capacity_weekly w ON f.property = w.property
        GROUP BY f.feedlot_name, f.target_utilization_pct""")
    facts = "\n".join(
        f"- {r['feedlot_name']}: currently ~{r['current_util']}% utilised against a {r['target_utilization_pct']}% target"
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
