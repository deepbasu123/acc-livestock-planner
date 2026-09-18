#!/usr/bin/env python3
"""Build the ACC Livestock Planner Lakeview dashboard."""
import json, subprocess, uuid, os

PROFILE = os.environ.get("ACC_PROFILE", "DEFAULT")
WAREHOUSE = os.environ["ACC_WAREHOUSE"]
PARENT = os.environ.get("ACC_PARENT", "/Workspace/Shared/acc-livestock-planner")
CAT = os.environ.get("ACC_CATALOG", "deep_test_1_catalog")
NAVY = "#002A54"; GOLD = "#C9A227"; GREEN = "#1E7E34"; RED = "#DC3545"; AMBER = "#B8860B"; SLATE = "#6C757D"
PALETTE = [NAVY, GOLD, GREEN, RED, AMBER, SLATE, "#4A90E2", "#8BA6C1"]


def wid():
    return uuid.uuid4().hex[:8]


DS_BOOKINGS = wid(); DS_CAPACITY = wid(); DS_VENDORS = wid(); DS_AGENTS = wid(); DS_PRICE = wid()
datasets = [
    {"name": DS_BOOKINGS, "displayName": "Bookings", "queryLines": [
        "SELECT id, property, feedlot_name, vendor_name, agent_name, buyer_name, status, ",
        "CASE WHEN status='Cancelled' THEN 1 ELSE 0 END AS is_cancelled, head_count, week_commencing, price_per_kg_numeric ",
        f"FROM {CAT}.acc_gold.booking_expanded"]},
    {"name": DS_CAPACITY, "displayName": "Feedlot Capacity Weekly", "queryLines": [
        "SELECT property, feedlot_name, week_start, total_capacity_head, head_booked, head_on_feed_est, utilization_pct ",
        f"FROM {CAT}.acc_gold.feedlot_capacity_weekly ORDER BY week_start"]},
    {"name": DS_VENDORS, "displayName": "Vendor Scorecard", "queryLines": [
        "SELECT vendor_name, total_bookings, cancelled_bookings, cancellation_rate_pct, total_head_booked, avg_price_per_kg ",
        f"FROM {CAT}.acc_gold.vendor_scorecard WHERE total_bookings > 0 ORDER BY total_head_booked DESC"]},
    {"name": DS_AGENTS, "displayName": "Agent Performance", "queryLines": [
        "SELECT agent_name, total_bookings, total_head_booked, distinct_vendors ",
        f"FROM {CAT}.acc_gold.agent_performance WHERE total_bookings > 0 ORDER BY total_bookings DESC"]},
    {"name": DS_PRICE, "displayName": "Price Trend", "queryLines": [
        "SELECT property, feedlot_name, week_start, avg_price_per_kg ",
        f"FROM {CAT}.acc_gold.price_trend_weekly ORDER BY week_start"]},
]


def text(name, md, x, y, w, h):
    return {"widget": {"name": name, "multilineTextboxSpec": {"lines": [md]}},
            "position": {"x": x, "y": y, "width": w, "height": h}}


def counter(name, ds, fname, expr, title, x, y, fmt=None, w=2, h=3):
    val = {"fieldName": fname, "displayName": title}
    if fmt:
        val["format"] = fmt
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": [{"name": fname, "expression": expr}], "disaggregated": False}}],
        "spec": {"version": 2, "widgetType": "counter",
                 "encodings": {"value": val},
                 "frame": {"showTitle": True, "title": title}}},
        "position": {"x": x, "y": y, "width": w, "height": h}}


def bar(name, ds, xf, xexpr, yf, yexpr, title, x, y, w=3, h=6, sort_y=False, colors=None):
    fields = [{"name": xf, "expression": xexpr}, {"name": yf, "expression": yexpr}]
    xscale = {"type": "categorical"}
    if sort_y:
        xscale["sort"] = {"by": "y-reversed"}
    enc = {"x": {"fieldName": xf, "scale": xscale, "displayName": xf},
           "y": {"fieldName": yf, "scale": {"type": "quantitative"}, "displayName": yf},
           "label": {"show": True}}
    spec = {"version": 3, "widgetType": "bar", "encodings": enc,
            "frame": {"showTitle": True, "title": title}, "mark": {"colors": colors or PALETTE}}
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": fields, "disaggregated": False}}], "spec": spec},
        "position": {"x": x, "y": y, "width": w, "height": h}}


def line(name, ds, xf, xexpr, yf, yexpr, title, x, y, w=3, h=6, color=None, colors=None):
    fields = [{"name": xf, "expression": xexpr}, {"name": yf, "expression": yexpr}]
    enc = {"x": {"fieldName": xf, "scale": {"type": "temporal"}, "displayName": "Week"},
           "y": {"fieldName": yf, "scale": {"type": "quantitative"}, "displayName": yf}}
    if color:
        cf, cexpr = color
        fields.append({"name": cf, "expression": cexpr})
        enc["color"] = {"fieldName": cf, "scale": {"type": "categorical"}, "displayName": cf}
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": fields, "disaggregated": False}}],
        "spec": {"version": 3, "widgetType": "line", "encodings": enc,
                 "frame": {"showTitle": True, "title": title}, "mark": {"colors": colors or [NAVY, GOLD, SLATE]}}},
        "position": {"x": x, "y": y, "width": w, "height": h}}


def pie(name, ds, af, aexpr, cf, cexpr, title, x, y, w=3, h=6, mappings=None):
    cscale = {"type": "categorical"}
    if mappings:
        cscale["mappings"] = mappings
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": [{"name": af, "expression": aexpr}, {"name": cf, "expression": cexpr}],
        "disaggregated": False}}],
        "spec": {"version": 3, "widgetType": "pie",
                 "encodings": {"angle": {"fieldName": af, "scale": {"type": "quantitative"}, "displayName": af},
                               "color": {"fieldName": cf, "scale": cscale, "displayName": cf}},
                 "frame": {"showTitle": True, "title": title}}},
        "position": {"x": x, "y": y, "width": w, "height": h}}


def table(name, ds, cols, title, x, y, w=6, h=7):
    fields = [{"name": c[0], "expression": f"`{c[0]}`"} for c in cols]
    columns = [{"fieldName": c[0], "displayName": c[1]} for c in cols]
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": fields, "disaggregated": True}}],
        "spec": {"version": 2, "widgetType": "table", "encodings": {"columns": columns},
                 "frame": {"showTitle": True, "title": title}}},
        "position": {"x": x, "y": y, "width": w, "height": h}}


STATUS_MAP = [{"value": "Confirmed", "color": GREEN}, {"value": "Draft", "color": SLATE}, {"value": "Cancelled", "color": RED}]

# ---------------- Page 1: Bookings Overview ----------------
p1 = [
    text("p1-title", "# ACC Livestock Planner", 0, 0, 6, 1),
    text("p1-sub", "Cattle bookings across three feedlots — one row per booking, governed by Unity Catalog.", 0, 1, 6, 1),
    counter("p1-c1", DS_BOOKINGS, "count(id)", "COUNT(`id`)", "Total Bookings", 0, 2),
    counter("p1-c2", DS_BOOKINGS, "sum(head_count)", "SUM(`head_count`)", "Total Head Booked", 2, 2),
    counter("p1-c3", DS_BOOKINGS, "sum(is_cancelled)", "SUM(`is_cancelled`)", "Cancelled Bookings", 4, 2),
    counter("p1-c4", DS_CAPACITY, "max(utilization_pct)", "MAX(`utilization_pct`)", "Peak Feedlot Utilisation %", 0, 5),
    counter("p1-c5", DS_BOOKINGS, "count(distinct vendor_name)", "COUNT(DISTINCT `vendor_name`)", "Active Vendors", 2, 5),
    counter("p1-c6", DS_BOOKINGS, "count(distinct agent_name)", "COUNT(DISTINCT `agent_name`)", "Active Agents", 4, 5),
    text("p1-h1", "## Bookings", 0, 8, 6, 1),
    bar("p1-bar", DS_BOOKINGS, "feedlot_name", "`feedlot_name`", "sum(head_count)", "SUM(`head_count`)",
        "Head Count by Feedlot", 0, 9, 3, 6, sort_y=True),
    pie("p1-pie", DS_BOOKINGS, "count(id)", "COUNT(`id`)", "status", "`status`",
        "Bookings by Status", 3, 9, 3, 6, mappings=STATUS_MAP),
]

# ---------------- Page 2: Capacity & Market ----------------
p2 = [
    text("p2-title", "# Capacity & Market", 0, 0, 6, 1),
    text("p2-sub", "Feedlot capacity utilisation (estimated on-feed inventory vs pen capacity) and the weekly price trend.", 0, 1, 6, 1),
    counter("p2-c1", DS_CAPACITY, "max(week_start)", "MAX(`week_start`)", "Latest Week", 0, 2, w=3),
    counter("p2-c2", DS_CAPACITY, "avg(utilization_pct)", "AVG(`utilization_pct`)", "Avg Utilisation %", 3, 2, w=3),
    text("p2-h1", "## Capacity", 0, 5, 6, 1),
    line("p2-line1", DS_CAPACITY, "week", "`week_start`", "utilization_pct", "`utilization_pct`",
         "Utilisation % by Feedlot (weekly)", 0, 6, 3, 7, color=("feedlot_name", "`feedlot_name`")),
    bar("p2-bar1", DS_CAPACITY, "feedlot_name", "`feedlot_name`", "avg(head_on_feed_est)", "AVG(`head_on_feed_est`)",
        "Avg Estimated On-Feed Head", 3, 6, 3, 7, sort_y=True),
    text("p2-h2", "## Market", 0, 13, 6, 1),
    line("p2-line2", DS_PRICE, "week", "`week_start`", "avg_price_per_kg", "`avg_price_per_kg`",
         "Avg Price per Kg by Feedlot", 0, 14, 6, 7, color=("feedlot_name", "`feedlot_name`")),
]

# ---------------- Page 3: Vendors & Agents ----------------
p3 = [
    text("p3-title", "# Vendors & Agents", 0, 0, 6, 1),
    text("p3-sub", "Vendor and agent performance across the booking network.", 0, 1, 6, 1),
    counter("p3-c1", DS_VENDORS, "count(vendor_name)", "COUNT(`vendor_name`)", "Active Vendors", 0, 2),
    counter("p3-c2", DS_VENDORS, "avg(cancellation_rate_pct)", "AVG(`cancellation_rate_pct`)", "Avg Cancellation %", 2, 2),
    counter("p3-c3", DS_AGENTS, "count(agent_name)", "COUNT(`agent_name`)", "Active Agents", 4, 2),
    text("p3-h1", "## Top Vendors", 0, 5, 6, 1),
    bar("p3-bar1", DS_VENDORS, "vendor_name", "`vendor_name`", "sum(total_head_booked)", "SUM(`total_head_booked`)",
        "Head Booked by Vendor (top 10)", 0, 6, 6, 6, sort_y=True),
    text("p3-h2", "## Vendor Scorecard", 0, 12, 6, 1),
    table("p3-tbl", DS_VENDORS, [
        ("vendor_name", "Vendor"), ("total_bookings", "Bookings"), ("cancellation_rate_pct", "Cancel %"),
        ("total_head_booked", "Head Booked"), ("avg_price_per_kg", "Avg $/Kg")],
        "Vendor Scorecard", 0, 13, 6, 7),
    text("p3-h3", "## Agent Performance", 0, 20, 6, 1),
    table("p3-tbl2", DS_AGENTS, [
        ("agent_name", "Agent"), ("total_bookings", "Bookings"), ("total_head_booked", "Head Booked"), ("distinct_vendors", "Vendors")],
        "Agent Performance", 0, 21, 6, 7),
]

pages = [
    {"name": wid(), "displayName": "Bookings Overview", "pageType": "PAGE_TYPE_CANVAS", "layout": p1},
    {"name": wid(), "displayName": "Capacity & Market", "pageType": "PAGE_TYPE_CANVAS", "layout": p2},
    {"name": wid(), "displayName": "Vendors & Agents", "pageType": "PAGE_TYPE_CANVAS", "layout": p3},
]

serialized = {"datasets": datasets, "pages": pages,
              "uiSettings": {"theme": {"widgetHeaderAlignment": "ALIGNMENT_UNSPECIFIED"}}}

payload = {"display_name": "ACC Livestock Planner", "warehouse_id": WAREHOUSE,
           "parent_path": PARENT, "serialized_dashboard": json.dumps(serialized)}

with open("/tmp/acc_dash.json", "w") as f:
    json.dump(payload, f)

out = subprocess.check_output(
    ["databricks", "api", "post", "/api/2.0/lakeview/dashboards", "--profile", PROFILE,
     "--json", "@/tmp/acc_dash.json"], text=True)
resp = json.loads(out)
print("DASHBOARD_ID:", resp.get("dashboard_id"))
print(json.dumps({k: resp.get(k) for k in ("dashboard_id", "display_name", "path")}, indent=2))
