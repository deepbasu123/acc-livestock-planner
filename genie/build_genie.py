#!/usr/bin/env python3
"""Author the ACC Livestock Planner Genie space via REST."""
import json, subprocess, uuid, sys, os

PROFILE = os.environ.get("ACC_PROFILE", "DEFAULT")
WAREHOUSE = os.environ["ACC_WAREHOUSE"]
PARENT = os.environ.get("ACC_PARENT", "/Workspace/Shared/acc-livestock-planner")
CAT = os.environ.get("ACC_CATALOG", "")


def hid():
    return uuid.uuid4().hex


TABLES = sorted([
    f"{CAT}.acc_gold.booking_expanded",
    f"{CAT}.acc_gold.feedlot_capacity_weekly",
    f"{CAT}.acc_gold.vendor_scorecard",
    f"{CAT}.acc_gold.agent_performance",
    f"{CAT}.acc_gold.price_trend_weekly",
    f"{CAT}.acc_feedlot.feedlots",
    f"{CAT}.acc_audit.booking_history",
])

ENTITY_COLS = {
    f"{CAT}.acc_gold.booking_expanded": ["property", "feedlot_name", "vendor_name", "agent_name", "buyer_name", "status"],
    f"{CAT}.acc_gold.vendor_scorecard": ["vendor_name"],
    f"{CAT}.acc_gold.agent_performance": ["agent_name"],
    f"{CAT}.acc_feedlot.feedlots": ["feedlot_name", "property"],
}

tables_payload = []
for t in TABLES:
    cfgs = []
    for col in sorted(ENTITY_COLS.get(t, [])):
        cfgs.append({"column_name": col, "enable_format_assistance": True, "enable_entity_matching": True})
    entry = {"identifier": t}
    if cfgs:
        entry["column_configs"] = cfgs
    tables_payload.append(entry)

INSTRUCTIONS = (
    "This Genie Space is the ACC Livestock Procurement Planner, for Australian Country Choice (ACC), a "
    "(fictional-data) 100% Australian, family-owned beef supply chain business. It replaces per-feedlot "
    "Excel spreadsheets with one central booking system for three feedlots: BPFL (Brindley Park), Opal Ck "
    "(Opal Creek) and BVFL (Burnett Valley). "
    "The star table is acc_gold.booking_expanded - one row per cattle booking (soft-deleted rows already "
    "excluded) with every foreign key resolved to a name: agent_name, vendor_name, payee_name, "
    "weigh_point_name, origin_name, buyer_name. status is Draft, Confirmed or Cancelled. price_per_kg is "
    "free text entered by field staff (e.g. '6.80', '6.80 c/kg') - price_per_kg_numeric is a best-effort "
    "parsed numeric version, use it for aggregation and note it can be NULL when the text didn't parse. "
    "Some pricing columns (price_per_kg, price_variation, buyer_payee_details) are governed by Unity "
    "Catalog ABAC and may appear REDACTED depending on the viewer's persona group (Executive, Procurement, "
    "Operations) - this is expected. "
    "acc_gold.feedlot_capacity_weekly has one row per feedlot per week with head_booked, a rolling 14-week "
    "head_on_feed_est (an estimate - there is no separate receival system) and utilization_pct against "
    "total_capacity_head - use this for capacity/utilisation questions. "
    "acc_gold.vendor_scorecard and acc_gold.agent_performance summarise booking volume, cancellation rate "
    "and price by vendor/agent. acc_audit.booking_history is an append-only log of create/update/delete/"
    "duplicate actions on bookings - use it for 'who changed what' questions."
)


def sql_lines(s):
    return [l + "\n" for l in s.strip().split("\n")]


EXAMPLES = [
    ("Which feedlot is closest to capacity right now?",
     "SELECT feedlot_name, week_start, head_on_feed_est, total_capacity_head, utilization_pct\n"
     f"FROM {CAT}.acc_gold.feedlot_capacity_weekly\nWHERE week_start = (SELECT MAX(week_start) FROM {CAT}.acc_gold.feedlot_capacity_weekly)\n"
     "ORDER BY utilization_pct DESC"),
    ("Total head count booked by feedlot this month?",
     "SELECT feedlot_name, SUM(head_count) AS head_booked, COUNT(*) AS bookings\n"
     f"FROM {CAT}.acc_gold.booking_expanded\nWHERE status <> 'Cancelled' AND DATE_TRUNC('MONTH', week_commencing) = DATE_TRUNC('MONTH', CURRENT_DATE())\n"
     "GROUP BY feedlot_name ORDER BY head_booked DESC"),
    ("Which vendors have the highest cancellation rate?",
     "SELECT vendor_name, total_bookings, cancellation_rate_pct\n"
     f"FROM {CAT}.acc_gold.vendor_scorecard\nWHERE total_bookings >= 5\nORDER BY cancellation_rate_pct DESC\nLIMIT 10"),
    ("Which agents handle the most bookings?",
     "SELECT agent_name, total_bookings, total_head_booked, distinct_vendors\n"
     f"FROM {CAT}.acc_gold.agent_performance\nORDER BY total_bookings DESC\nLIMIT 10"),
    ("What is our average price trend by feedlot?",
     "SELECT feedlot_name, week_start, avg_price_per_kg\n"
     f"FROM {CAT}.acc_gold.price_trend_weekly\nORDER BY week_start"),
    ("Who deleted a booking recently?",
     "SELECT booking_id, changed_by, changed_at, old_data\n"
     f"FROM {CAT}.acc_audit.booking_history\nWHERE action = 'delete'\nORDER BY changed_at DESC\nLIMIT 10"),
]

SAMPLE_Q = [
    "Which feedlot is closest to capacity this week?",
    "Total head count booked by feedlot this month?",
    "Which vendors have the highest cancellation rate?",
    "Which agents handle the most bookings?",
    "What is our average price trend by feedlot?",
]

sample_q = sorted([{"id": hid(), "question": [q]} for q in SAMPLE_Q], key=lambda x: x["id"])
text_instr = sorted([{"id": hid(), "content": [INSTRUCTIONS]}], key=lambda x: x["id"])
ex_sqls = sorted([{"id": hid(), "question": [q], "sql": sql_lines(s)} for q, s in EXAMPLES], key=lambda x: x["id"])

serialized = {
    "version": 2,
    "config": {"sample_questions": sample_q},
    "data_sources": {"tables": tables_payload},
    "instructions": {
        "text_instructions": text_instr,
        "example_question_sqls": ex_sqls,
    },
}

payload = {
    "title": "ACC Livestock Planner",
    "description": "Ask questions across ACC's cattle booking data - feedlot capacity, vendors, agents and pricing. One row per booking, every FK resolved to a name.",
    "parent_path": PARENT,
    "warehouse_id": WAREHOUSE,
    "serialized_space": json.dumps(serialized),
}

with open("/tmp/acc_genie_create.json", "w") as f:
    json.dump(payload, f)

out = subprocess.check_output(
    ["databricks", "api", "post", "/api/2.0/genie/spaces", "--profile", PROFILE,
     "--json", "@/tmp/acc_genie_create.json"], text=True)
resp = json.loads(out)
print("SPACE_ID:", resp.get("space_id") or resp.get("id"))
print(json.dumps({k: resp.get(k) for k in ("space_id", "title", "description")}, indent=2))
