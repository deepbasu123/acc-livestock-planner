"""AI features: feedlot health summary (Foundation Model API).

Reads the Lakebase gold views (see server/pg_bootstrap.py)."""
from fastapi import APIRouter
from pydantic import BaseModel

from .. import pg
from ..llm import chat

router = APIRouter()


class FeedlotReq(BaseModel):
    property: str


@router.post("/ai/feedlot-summary")
def feedlot_summary(req: FeedlotReq):
    f = pg.one("SELECT * FROM feedlots WHERE property = :p", {"p": req.property})
    if not f:
        return {"summary": "Feedlot not found."}
    latest = pg.one("""SELECT * FROM feedlot_capacity_weekly WHERE property = :p
        ORDER BY week_start DESC LIMIT 1""", {"p": req.property})
    stats = pg.one("""SELECT COUNT(*) AS bookings_90d,
               SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END) AS cancelled_count,
               SUM(CASE WHEN status <> 'Cancelled' THEN head_count ELSE 0 END) AS head_booked
        FROM booking_expanded
        WHERE property = :p AND week_commencing >= CURRENT_DATE - 90""", {"p": req.property})
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
