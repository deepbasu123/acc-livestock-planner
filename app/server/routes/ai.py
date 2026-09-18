"""AI features: feedlot health summary (Foundation Model API)."""
from fastapi import APIRouter
from pydantic import BaseModel
from ..sql import run, one
from ..llm import chat
from ..config import CATALOG

router = APIRouter()
G = f"{CATALOG}.acc_gold"
FL = f"{CATALOG}.acc_feedlot"


class FeedlotReq(BaseModel):
    property: str


@router.post("/ai/feedlot-summary")
def feedlot_summary(req: FeedlotReq):
    f = one(f"SELECT * FROM {FL}.feedlots WHERE property = '{req.property}'")
    if not f:
        return {"summary": "Feedlot not found."}
    latest = one(f"""SELECT * FROM {G}.feedlot_capacity_weekly WHERE property = '{req.property}'
        ORDER BY week_start DESC LIMIT 1""")
    stats = one(f"""SELECT COUNT(*) AS bookings_90d,
               SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END) AS cancelled_count,
               SUM(CASE WHEN status <> 'Cancelled' THEN head_count ELSE 0 END) AS head_booked
        FROM {G}.booking_expanded
        WHERE property = '{req.property}' AND week_commencing >= DATE_SUB(CURRENT_DATE(), 90)""")
    facts = (
        f"Feedlot: {f.get('feedlot_name')} ({f.get('property')}), {f.get('suburb')} {f.get('state')}\n"
        f"Total pen capacity: {f.get('total_capacity_head')} head | Target utilisation: {f.get('target_utilization_pct')}%\n"
        f"Latest estimated on-feed: {latest.get('head_on_feed_est') if latest else 'n/a'} head "
        f"({latest.get('utilization_pct') if latest else 'n/a'}% of capacity)\n"
        f"Last 90 days: {stats.get('bookings_90d')} bookings, {stats.get('head_booked')} head booked, "
        f"{stats.get('cancelled_count')} cancelled"
    )
    msgs = [
        {"role": "system", "content": (
            "You are an operations analyst for Australian Country Choice (ACC), a vertically integrated "
            "Australian beef company. Write a crisp feedlot health briefing for the procurement manager. Use "
            "Australian English. Be specific and quantitative. Structure: a one-line status verdict, then 3-4 "
            "bullet points on capacity and booking activity, then 2-3 recommended actions. No preamble. Under "
            "180 words.")},
        {"role": "user", "content": f"Brief me on this feedlot:\n\n{facts}"},
    ]
    try:
        summary = chat(msgs, max_tokens=600)
    except Exception as e:
        summary = f"(AI summary unavailable: {e})"
    return {"property": req.property, "summary": summary}
