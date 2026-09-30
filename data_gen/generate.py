#!/usr/bin/env python3
"""ACC Livestock Procurement Planner - synthetic data generator.

Reproduces the real app's data model exactly (see docs/SPEC.md from the
reference implementation): a `cattle_bookings` table booking cattle into one
of three ACC feedlots (BPFL, Opal Ck, BVFL), seven managed master-data lists
(agents, vendors, payees, programs, weigh_points, origins, buyers), and an
append-only `booking_history` audit log. A `feedlots` master table (capacity/
location) is added as a Databricks-flavoured bonus that drives the Capacity
Forecast tab; it does not exist in the reference app.

Five source systems -> out/<schema>/<table>.parquet:
  acc_feedlot     feedlots
  acc_counterparty agents, vendors, payees, buyers
  acc_reference   programs, weigh_points, origins
  acc_booking     cattle_bookings
  acc_audit       booking_history

Deterministic (seeded). Australian conventions throughout. Every vendor/agent
carries its own "DNA" (propensities) so booking volume differs between
entities instead of clustering - see references/data-customization.md.
"""
import datetime as dt
import json
import random
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
rng = np.random.default_rng(SEED)

TODAY = dt.date(2026, 9, 18)
HIST_START = dt.date(2025, 7, 1)
FCAST_END = TODAY + dt.timedelta(weeks=12)
OUT = Path(__file__).parent / "out"


def uid():
    return str(uuid.uuid4())


def rand_date(start, end):
    if isinstance(start, dt.datetime):
        start = start.date()
    if isinstance(end, dt.datetime):
        end = end.date()
    days = (end - start).days
    if days <= 0:
        return start
    return start + dt.timedelta(days=int(rng.integers(0, days)))


def rand_ts(d, start_h=6, end_h=18):
    return dt.datetime.combine(d, dt.time(int(rng.integers(start_h, end_h)), int(rng.choice([0, 15, 30, 45]))))


# ISO week helpers, matching src/lib/week.ts in the reference app exactly.
def get_iso_week(d):
    iso = d.isocalendar()
    return iso[1], iso[0]


def iso_week_string(d):
    week, year = get_iso_week(d)
    return f"{year}-W{week:02d}"


def week_commencing(d):
    return d - dt.timedelta(days=d.weekday())


SEASONAL_MULT = {1: 0.55, 2: 0.55, 3: 0.70, 4: 1.05, 5: 1.25, 6: 1.30,
                 7: 1.30, 8: 1.25, 9: 1.15, 10: 1.05, 11: 0.85, 12: 0.60}

# ----------------------------------------------------------------------------
# Reference pools
# ----------------------------------------------------------------------------
FIRST_NAMES = ["James", "Oliver", "Jack", "William", "Noah", "Thomas", "Lucas", "Henry", "Liam", "Cooper",
    "Charlie", "Mason", "Alexander", "Ethan", "Lachlan", "Harrison", "Max", "Leo", "Hudson", "Archie",
    "Olivia", "Charlotte", "Amelia", "Isla", "Mia", "Ava", "Grace", "Chloe", "Sophie", "Ruby",
    "Angus", "Bradley", "Colin", "Douglas", "Gordon", "Hamish", "Iain", "Rhys", "Trent", "Wade",
    "Emily", "Zoe", "Harper", "Evie", "Ella", "Matilda", "Sofia", "Layla", "Lily", "Maya"]
LAST_NAMES = ["Smith", "Jones", "Williams", "Brown", "Wilson", "Taylor", "Nguyen", "Lee", "Martin", "Anderson",
    "White", "Thompson", "Walker", "Harris", "Clarke", "Lewis", "Young", "King", "Wright", "Hill",
    "Scott", "Green", "Adams", "Baker", "Nelson", "Mitchell", "Roberts", "Campbell", "Turner", "Parker",
    "McKenzie", "Fraser", "Robertson", "Docherty", "Ferguson", "Sinclair", "Pfeffer", "Schmidt", "Krause", "Zerner"]
TOWNS = [
    ("Dalby", "QLD"), ("Chinchilla", "QLD"), ("Roma", "QLD"), ("Miles", "QLD"), ("Goondiwindi", "QLD"),
    ("St George", "QLD"), ("Charleville", "QLD"), ("Emerald", "QLD"), ("Clermont", "QLD"), ("Biloela", "QLD"),
    ("Gayndah", "QLD"), ("Mundubbera", "QLD"), ("Kingaroy", "QLD"), ("Warwick", "QLD"), ("Stanthorpe", "QLD"),
    ("Injune", "QLD"), ("Taroom", "QLD"), ("Theodore", "QLD"), ("Blackall", "QLD"), ("Longreach", "QLD"),
    ("Moura", "QLD"), ("Moree", "NSW"), ("Narrabri", "NSW"), ("Inverell", "NSW"), ("Tenterfield", "NSW"),
    ("Walgett", "NSW"), ("Boggabilla", "NSW"),
]
FEEDLOT_TOWNS = {"BPFL": ("Dalby", "QLD"), "Opal Ck": ("Clermont", "QLD"), "BVFL": ("Gayndah", "QLD")}
PROPERTY_WORDS_1 = ["Brindley", "Coolibah", "Wattle", "Boonderoo", "Yaraka", "Nindigully", "Warroo", "Carinya",
    "Tara", "Barambah", "Myall", "Bimbadeen", "Gunyah", "Ironbark", "Yandilla", "Cooinda", "Wallaroo",
    "Talgai", "Boondara", "Wongalee", "Kalinga", "Mundoora", "Bellbird", "Yalgoo", "Tarwonga", "Currawong",
    "Belah", "Yamburra", "Dilkoon", "Marlee", "Terrigal", "Nulla", "Broombee", "Kooroongarra", "Warra",
    "Anembo", "Boorala", "Cungelella", "Dunmore", "Eidsvold", "Glenora"]
PROPERTY_WORDS_2 = ["Downs", "Station", "Plains", "Park", "Grove", "Vale", "Creek", "Springs", "Hills", "Run"]

AGENT_NAMES = ["Downs Rural Agents", "Western Livestock Agency", "Channel Country Stock Agents",
    "Golden Triangle Rural", "Highlands Livestock & Property", "Southern Cross Rural Agency",
    "Border Rivers Stock Agents", "Maranoa Rural Co", "Burnett Livestock Agents", "Granite Belt Rural",
    "Darling Downs Stock & Station", "Central West Rural Agency", "Outback Livestock Brokers",
    "Fitzroy Rural Agents", "North West Stock Agency", "Range Country Rural", "Big Sky Livestock Agency",
    "Coastal Plains Stock Agents"]
PAYEE_SUFFIX = ["Pastoral Trust", "Grazing Co Pty Ltd", "Family Trust", "Superannuation Fund", "Pty Ltd", "& Sons"]
PROGRAM_NAMES = ["MSA Grid Program", "Grass Fed Program", "Grain Assisted Program", "EU Accredited Program",
    "HGP-Free Program", "Live Export Program", "Domestic Trade Program", "Branded Beef Program",
    "Certified Angus Program", "Organic Beef Program"]
ORIGIN_REGIONS = ["Darling Downs", "Western Downs", "Maranoa", "Central Highlands", "North Burnett",
    "South Burnett", "South West QLD", "Channel Country", "Granite Belt", "Border Rivers",
    "North West NSW", "Fitzroy Basin", "Central QLD", "Southern Downs", "Wide Bay", "Gulf Country"]

BOOKING_STATUSES = ["Draft", "Confirmed", "Cancelled"]
DELIVERY_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
NOTES_POOL = ["Vendor requests early morning delivery", "Split consignment, second load to follow",
    "Drought-affected line, monitor condition", "Repeat booking from last week, same specs",
    "Horned cattle, segregate on arrival", "Weight slip required on arrival", "Buyer to confirm grid before delivery",
    "First booking from this vendor", "Agent to arrange transport", "Price subject to final weight"]


def add_history(rows, booking_id, action, changed_by, changed_by_email, changed_at, old_data, new_data):
    rows.append(dict(
        id=uid(), booking_id=booking_id, action=action, changed_by=changed_by, changed_by_email=changed_by_email,
        changed_at=changed_at, old_data=json.dumps(old_data) if old_data is not None else None,
        new_data=json.dumps(new_data) if new_data is not None else None,
    ))


tables = {}


def add(schema, table, df):
    tables[(schema, table)] = df
    print(f"  {schema}.{table}: {len(df)} rows")


# ============================================================================
# 1. FEEDLOT MASTER DATA (bonus - drives the Capacity Forecast tab)
# ============================================================================
print("Generating feedlots (bonus master data)...")
FEEDLOT_DEF = [
    dict(property="BPFL", feedlot_name="Brindley Park Feedlot", total_capacity_head=32000, popularity=1.35, target_utilization_pct=82.0),
    dict(property="Opal Ck", feedlot_name="Opal Creek Feedlot", total_capacity_head=18500, popularity=0.85, target_utilization_pct=93.0),
    dict(property="BVFL", feedlot_name="Burnett Valley Feedlot", total_capacity_head=24000, popularity=1.05, target_utilization_pct=76.0),
]
feedlots = []
for f in FEEDLOT_DEF:
    town, state = FEEDLOT_TOWNS[f["property"]]
    feedlots.append(dict(property=f["property"], feedlot_name=f["feedlot_name"], suburb=town, state=state,
        total_capacity_head=f["total_capacity_head"], target_utilization_pct=f["target_utilization_pct"]))
add("acc_feedlot", "feedlots", pd.DataFrame(feedlots))
PROPERTIES = [f["property"] for f in FEEDLOT_DEF]
FL_POPULARITY = {f["property"]: f["popularity"] for f in FEEDLOT_DEF}
FL_CAPACITY = {f["property"]: f["total_capacity_head"] for f in FEEDLOT_DEF}

# ============================================================================
# 2. COUNTERPARTIES: agents, vendors, payees, buyers
# ============================================================================
print("Generating counterparties (agents, vendors, payees, buyers)...")


def master_row(name, active_p=0.95):
    created = rand_date(dt.date(2018, 1, 1), dt.date(2026, 6, 1))
    return dict(id=uid(), name=name, active=bool(rng.random() < active_p),
                created_at=rand_ts(created), updated_at=rand_ts(rand_date(created, TODAY)))


agents = [master_row(n) for n in AGENT_NAMES]
for a in random.sample(agents, k=2):  # agency ceased operating / consolidated
    a["active"] = False
add("acc_counterparty", "agents", pd.DataFrame(agents))
AGENT_DNA = {a["id"]: float(rng.lognormal(0, 0.7)) for a in agents}

N_VENDORS = 105
vendors = []
used_names = set()
for _ in range(N_VENDORS):
    name = f"{random.choice(PROPERTY_WORDS_1)} {random.choice(PROPERTY_WORDS_2)}"
    if name in used_names:
        _, state = random.choice(TOWNS)
        name = f"{name} ({state})" if f"{name} ({state})" not in used_names else f"{name} #{rng.integers(2,99)}"
    used_names.add(name)
    vendors.append(master_row(name))
add("acc_counterparty", "vendors", pd.DataFrame(vendors))
VENDOR_SCALE = {}
for v in vendors:
    # Sharper tiering (fewer, bigger key accounts) for a realistic Pareto skew.
    tier = random.choices(["key", "big", "mid", "small"], [0.06, 0.14, 0.35, 0.45])[0]
    VENDOR_SCALE[v["id"]] = {"key": rng.uniform(4.5, 7.0), "big": rng.uniform(2.2, 3.6),
                             "mid": rng.uniform(0.9, 1.8), "small": rng.uniform(0.25, 0.75)}[tier]

payees = []
for v in vendors:
    if rng.random() < 0.7:  # most vendors are their own payee (same trading name)
        payees.append(master_row(f"{v['name']} {random.choice(PAYEE_SUFFIX)}"))
add("acc_counterparty", "payees", pd.DataFrame(payees))

buyers = [master_row(f"{fn[0]}. {ln}") for fn, ln in
          {(random.choice(FIRST_NAMES), random.choice(LAST_NAMES)) for _ in range(11)}]
for b in random.sample(buyers, k=2):  # a couple of buyers have left ACC - kept for history, hidden from new bookings
    b["active"] = False
add("acc_counterparty", "buyers", pd.DataFrame(buyers))

AGENT_IDS = [a["id"] for a in agents]
VENDOR_IDS = [v["id"] for v in vendors]
PAYEE_IDS = [p["id"] for p in payees]
BUYER_IDS = [b["id"] for b in buyers]

# ============================================================================
# 3. REFERENCE DATA: programs, weigh_points, origins
# ============================================================================
print("Generating reference data (programs, weigh points, origins)...")
programs = [master_row(n) for n in PROGRAM_NAMES]
add("acc_reference", "programs", pd.DataFrame(programs))

weigh_points = [master_row(f"{t} Weighbridge") for t, _ in TOWNS[:14]]
for w in random.sample(weigh_points, k=3):  # decommissioned / out of service
    w["active"] = False
add("acc_reference", "weigh_points", pd.DataFrame(weigh_points))

origins = [master_row(n) for n in ORIGIN_REGIONS]
for o in random.sample(origins, k=2):
    o["active"] = False
add("acc_reference", "origins", pd.DataFrame(origins))

PROGRAM_NAMES_ACTIVE = [p["name"] for p in programs if p["active"]]
WEIGH_POINT_IDS = [w["id"] for w in weigh_points]
ORIGIN_IDS = [o["id"] for o in origins]

# ============================================================================
# 4. CATTLE BOOKINGS (the hero table)
# ============================================================================
print("Generating cattle bookings...")
N_BOOKINGS = 1300
total_days = (FCAST_END - HIST_START).days
days = [HIST_START + dt.timedelta(days=d) for d in range(total_days + 1)]
day_weights = np.array([SEASONAL_MULT[d.month] * (1 + 0.08 * ((d - HIST_START).days / 365.0)) for d in days])
day_weights = day_weights / day_weights.sum()
chosen_days = sorted(rng.choice(days, size=N_BOOKINGS, p=day_weights, replace=True).tolist())

vendor_weights = np.array([VENDOR_SCALE[v] for v in VENDOR_IDS])
vendor_weights = vendor_weights / vendor_weights.sum()
agent_weights = np.array([AGENT_DNA[a] for a in AGENT_IDS])
agent_weights = agent_weights / agent_weights.sum()

vendor_payee = {}  # remember each vendor's usual payee for consistency
vendor_to_payee_pool = PAYEE_IDS if PAYEE_IDS else VENDOR_IDS


def price_text(base_ckg):
    """Free-text price field - deliberately messy real-world *labelling*
    (plain / labelled / dollar-sign), but the underlying number always stays
    in the same $/kg magnitude so aggregate numeric parsing isn't corrupted
    by a stray unit-scale error. Always populated so demo screens never show
    a blank Price/Kg cell."""
    v = round(max(4.2, base_ckg + rng.normal(0, 0.15)), 2)
    fmt = random.choices(["plain", "ckg", "dollar"], [0.50, 0.30, 0.20])[0]
    if fmt == "plain":
        return f"{v:.2f}"
    if fmt == "ckg":
        return f"{v:.2f} c/kg"
    return f"${v:.2f}/kg"


bookings = []
history_rows = []
STAFF = [f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}" for _ in range(9)]
STAFF_EMAIL = {n: f"{n.split()[0].lower()}.{n.split()[1].lower()}@accbeef.net.au" for n in STAFF}

for d in chosen_days:
    d = d if isinstance(d, dt.date) else d.tolist()
    is_future = d > TODAY
    prop = random.choices(PROPERTIES, [FL_POPULARITY[p] for p in PROPERTIES])[0]
    vendor_id = str(np.random.choice(VENDOR_IDS, p=vendor_weights))
    agent_id = str(np.random.choice(AGENT_IDS, p=agent_weights))
    if vendor_id not in vendor_payee and PAYEE_IDS:
        vendor_payee[vendor_id] = random.choice(PAYEE_IDS)
    payee_id = vendor_payee.get(vendor_id) or (random.choice(PAYEE_IDS) if PAYEE_IDS else None)

    lead_days = int(rng.integers(3, 28))
    created = d - dt.timedelta(days=lead_days)
    if created < dt.date(2025, 6, 1):
        created = d - dt.timedelta(days=min(lead_days, 3))
    scale = VENDOR_SCALE[vendor_id]
    cap_ceiling = int(FL_CAPACITY[prop] * 0.10)
    head_count = int(np.clip(rng.lognormal(np.log(60 * scale), 0.55), 15, cap_ceiling))

    if is_future:
        status = random.choices(BOOKING_STATUSES, [0.38, 0.57, 0.05])[0]
    else:
        status = random.choices(BOOKING_STATUSES, [0.03, 0.90, 0.07])[0]

    wc = week_commencing(d)
    week_number = iso_week_string(wc)
    base_price = {"BPFL": 6.35, "Opal Ck": 6.05, "BVFL": 6.55}[prop] + 0.9 * ((d - HIST_START).days / total_days)
    programs_pool = PROGRAM_NAMES_ACTIVE or PROGRAM_NAMES

    booking_id = uid()
    creator = random.choice(STAFF)
    row = dict(
        id=booking_id, property=prop, status=status,
        week_number=week_number, week_commencing=wc, head_count=head_count,
        delivery_day=random.choice(DELIVERY_DAYS),
        agent_id=agent_id, vendor_id=vendor_id, payee_id=payee_id,
        grid_text=f"{int(rng.integers(2400, 2900))}+{int(rng.integers(10, 40))}c",
        program=random.choice(programs_pool),
        price_per_kg=price_text(base_price),
        price_variation=random.choice(["ACC pays freight", "Vendor pays freight", "Subject to MSA grading",
            "Plus GST", "Weight loss allowance 2%", "Grid plus 10c if MSA 3+", "Subject to kill-out yield"]),
        weigh_point_id=random.choice(WEIGH_POINT_IDS),
        origin_id=random.choice(ORIGIN_IDS),
        buyer_id=random.choice(BUYER_IDS),
        buyer_payee_details=random.choice(["Pay on delivery", "30 day account", "EFT within 7 days", "Cash sale"]),
        notes=random.choice(NOTES_POOL),
        created_by=creator, created_by_email=STAFF_EMAIL[creator], created_at=rand_ts(created),
        modified_by=None, modified_by_email=None, updated_at=None, deleted_at=None,
    )
    row["updated_at"] = row["created_at"]
    bookings.append(row)
    add_history(history_rows, booking_id, "create", creator, STAFF_EMAIL[creator], row["created_at"], None,
                {k: (v.isoformat() if isinstance(v, (dt.date, dt.datetime)) else v) for k, v in row.items()})

    # ~35% of bookings get a later update (status change, price update, head count tweak)
    if rng.random() < 0.35 and not is_future:
        updater = random.choice(STAFF)
        update_at = rand_ts(min(TODAY, d + dt.timedelta(days=int(rng.integers(1, 10)))))
        old_snapshot = dict(row)
        if row["status"] == "Draft":
            row["status"] = random.choices(["Confirmed", "Cancelled"], [0.85, 0.15])[0]
        else:
            row["head_count"] = int(row["head_count"] * rng.uniform(0.9, 1.08))
        row["modified_by"] = updater
        row["modified_by_email"] = STAFF_EMAIL[updater]
        row["updated_at"] = update_at
        add_history(history_rows, booking_id, "update", updater, STAFF_EMAIL[updater], update_at,
                    {"status": old_snapshot["status"], "head_count": old_snapshot["head_count"]},
                    {"status": row["status"], "head_count": row["head_count"]})

# ~3% of bookings were duplicated from an earlier one (adds a couple of near-identical rows + a duplicate history event)
dup_source_rows = random.sample(bookings, k=int(len(bookings) * 0.03))
for src in dup_source_rows:
    dup_id = uid()
    dup_at = rand_ts(min(TODAY, dt.date.fromisoformat(str(src["created_at"].date() if isinstance(src["created_at"], dt.datetime) else src["created_at"])) + dt.timedelta(days=7)))
    dup = dict(src)
    dup.update(id=dup_id, status="Draft", created_by="ACC Livestock Planner", created_by_email="app@accbeef.net.au",
               created_at=dup_at, updated_at=dup_at, modified_by=None, modified_by_email=None, deleted_at=None)
    bookings.append(dup)
    add_history(history_rows, dup_id, "duplicate", "ACC Livestock Planner", "app@accbeef.net.au", dup_at,
                {"duplicated_from": src["id"]},
                {k: (v.isoformat() if isinstance(v, (dt.date, dt.datetime)) else v) for k, v in dup.items()})

# ~2.5% soft-deleted (still exist, excluded from lists)
del_candidates = [b for b in bookings if b["status"] != "Cancelled"]
for b in random.sample(del_candidates, k=max(1, int(len(bookings) * 0.025))):
    deleter = random.choice(STAFF)
    del_at = rand_ts(min(TODAY, (b["created_at"].date() if isinstance(b["created_at"], dt.datetime) else b["created_at"]) + dt.timedelta(days=int(rng.integers(1, 20)))))
    b["deleted_at"] = del_at
    add_history(history_rows, b["id"], "delete", deleter, STAFF_EMAIL[deleter], del_at, None, {"deleted_at": del_at.isoformat()})

bookings_df = pd.DataFrame(bookings)
filled_cols = [
    "property", "status", "week_number", "week_commencing", "head_count", "delivery_day",
    "agent_id", "vendor_id", "payee_id", "grid_text", "program", "price_per_kg", "price_variation",
    "weigh_point_id", "origin_id", "buyer_id", "buyer_payee_details", "notes", "created_by",
]
for c in filled_cols:
    nnull = int(bookings_df[c].isna().sum()) + int((bookings_df[c].astype(str).str.strip() == "").sum())
    if nnull:
        raise SystemExit(f"{c} has {nnull} blank values - expected fully populated synthetic data")
add("acc_booking", "cattle_bookings", bookings_df)

# ============================================================================
# 5. BOOKING HISTORY (append-only audit log)
# ============================================================================
history_df = pd.DataFrame(history_rows).sort_values("changed_at").reset_index(drop=True)
add("acc_audit", "booking_history", history_df)

# ============================================================================
# WRITE PARQUET
# ============================================================================
print("\nWriting parquet files...")
import shutil
import pyarrow as pa
import pyarrow.parquet as pq
if OUT.exists():
    shutil.rmtree(OUT)
total = 0
manifest = []
for (schema, table), df in tables.items():
    d = OUT / schema
    d.mkdir(parents=True, exist_ok=True)
    tbl = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(tbl, d / f"{table}.parquet", coerce_timestamps="us", allow_truncated_timestamps=True)
    total += len(df)
    manifest.append((schema, table, len(df)))

print(f"\nDONE. {len(tables)} tables, {total} total rows.")
print("\nManifest:")
for s, t, n in manifest:
    print(f"  {s}.{t}\t{n}")
