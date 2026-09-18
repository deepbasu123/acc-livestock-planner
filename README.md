# ACC Livestock Procurement Planner

A Databricks demo built for **Australian Country Choice (ACC)** — a 100% Australian,
family-owned, vertically integrated beef supply chain business. It reproduces the
functionality of ACC's real cattle-booking prototype (a TanStack Start app backed by
Postgres) as a native **Databricks App** (React + FastAPI) on top of **Unity
Catalog**, with the platform's own governance, natural-language and analytics
layers added on top.

Everything is synthetic and generated from a seeded script — there is no real ACC
data anywhere in this repo. You deploy it into your own workspace with one command.

## What it does

Replaces the per-feedlot Excel spreadsheets ACC's procurement team used to plan
cattle bookings into three feedlots — **BPFL** (Brindley Park), **Opal Ck** (Opal
Creek) and **BVFL** (Burnett Valley):

- **Dashboard** — total bookings, total head count, head count per feedlot, and
  three "+ New \<Feedlot\> Booking" shortcuts that deep-link into a pre-filled form.
- **Bookings** — search, filter (feedlot / status / week / buyer / agent / origin),
  and one-click Excel export of the filtered list with every foreign key resolved
  to a name.
- **Booking detail** — view/edit, **Duplicate** (copies the booking, resets status
  to Draft), soft **Delete** (never hard-deleted), and a full **change history**
  (a log of create/update/delete/duplicate events with old + new values, written
  by the app on every mutation; nothing in the UI ever issues an `UPDATE` or
  `DELETE` against it. Real immutability would additionally need to restrict UC
  grants so no identity holds `UPDATE`/`DELETE` on the table - Unity Catalog's
  `MODIFY` privilege doesn't split those out separately, so that's a follow-up,
  not something this demo enforces at the storage layer today).
- **Master Data** — manage the seven dropdown lists used on the booking form
  (Agents, Vendor Properties, Payees, Programs, Weigh Points, Origins, Buyers):
  add, rename, activate/deactivate, delete.

## What's added for the Databricks demo

The reference app is deliberately a simple booking CRUD tool (its own spec calls
out "no KPIs, analytics, charts, or executive dashboards"). On top of that exact
functionality, this rebuild adds the platform capabilities a customer conversation
usually wants to see, cleanly separated into their own tabs so the core workflow
stays uncluttered:

- **Capacity Forecast** — feedlot utilisation estimated from booked head count
  against pen capacity, plus a market price trend, with an AI-generated capacity
  strategy (Foundation Model API).
- **Governance** — Unity Catalog ABAC column masking on commercial pricing fields
  (`price_per_kg`, `price_variation`, `buyer_payee_details`), switchable live by
  persona (Executive / Procurement / Operations).
- **Ask ACC** — an embedded AI/BI Genie space for natural-language questions across
  the booking model.
- **Architecture** — a reference-architecture diagram, the masking policy table,
  and live deployed-object counts pulled from `information_schema`.

## Data model

Five source systems land in Unity Catalog and conform to one gold view:

```
acc_feedlot       feedlots (capacity/location — a Databricks-only addition,
                   not in the reference app, that drives Capacity Forecast)
acc_counterparty  agents, vendors, payees, buyers
acc_reference     programs, weigh_points, origins
acc_booking       cattle_bookings — the hero table, one row per booking
acc_audit         booking_history — the app only ever INSERTs new rows into
                  this table (see "the governance / persona demo" below for
                  what is and isn't enforced at the Unity Catalog layer)
acc_gold          booking_expanded (every FK resolved to a name) + supporting
                  views: feedlot_capacity_weekly, vendor_scorecard,
                  agent_performance, price_trend_weekly
```

`cattle_bookings` matches the reference schema field-for-field, including its
deliberately loose text fields (`price_per_kg`, `grid_text`, `week_number`) that
field staff fill in with real-world formats rather than a strict numeric type.
`acc_gold.booking_expanded` parses a best-effort numeric price
(`price_per_kg_numeric`) for aggregation without changing the source column.

## Prerequisites

- A Databricks workspace with Unity Catalog and a SQL warehouse (Serverless or Pro).
- The [Databricks CLI](https://docs.databricks.com/dev-tools/cli/index.html) installed and on PATH.
- Python 3.10+ (`pip install -r requirements.txt`).
- Node 18+ (only needed for `--with-app`, to build the React frontend).
- Permission to create (or write to) a catalog. Many shared/FE-VM workspaces have
  no default storage root configured for `CREATE CATALOG`; point `ACC_CATALOG` at
  an existing catalog instead — every schema here is prefixed `acc_` so it won't
  collide with anything else already in that catalog.

## Quick start

```bash
git clone <this-repo>
cd acc-livestock-planner
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. configure for your workspace
cp config.example.sh config.sh
$EDITOR config.sh                       # set profile, host, warehouse, catalog
source config.sh

# 2. authenticate the CLI (if you haven't)
databricks auth login --profile $ACC_PROFILE

# 3. deploy the data + analytics layer
python3 deploy.py

# 4. (optional) build + deploy the app too
python3 deploy.py --with-app
```

`deploy.py` runs these phases in order and is safe to re-run:

| Phase | What it does |
|---|---|
| provision | creates the catalog (if it can), the six schemas and a staging volume |
| data | generates the synthetic data, uploads it, loads each table via `read_files` CTAS |
| gold | builds the gold views, applies the commercial-pricing ABAC mask |
| genie | creates the Genie space and prints its id |
| dashboard | creates the Lakeview dashboard and prints its id |
| app | (with `--with-app`) builds the frontend, creates/deploys the app, grants its service principal access |

Run a single phase with `python3 deploy.py --only data`.

## The governance / persona demo

The mask in `sql/03_classification_abac.sql` gates `price_per_kg`,
`price_variation` and `buyer_payee_details` on group membership:

- `acc_exec` sees everything
- `acc_procurement` sees pricing
- `acc_operations` sees booking/logistics fields; pricing is masked
- no group: pricing is masked

These are workspace groups you create once:

```bash
databricks groups create --display-name acc_exec --profile $ACC_PROFILE
databricks groups create --display-name acc_procurement --profile $ACC_PROFILE
databricks groups create --display-name acc_operations --profile $ACC_PROFILE
```

Add yourself and the app's service principal to `acc_exec` (Admin Console →
Identity and access → Groups, or the SCIM API) to see unmasked data. The app's
**Governance** tab lets you flip personas and watch the same query redact
different columns live — the masking is enforced in Unity Catalog, so it applies
identically to the app, the dashboard, Genie and raw SQL.

## Repo layout

```
deploy.py                 one-command orchestrator
config.example.sh         deployment configuration (copy to config.sh)
data_gen/generate.py       seeded generator for the five source systems
sql/
  dbsql.py                SQL Statements API helper (used by the deployer)
  load_tables.py          load staged parquet into UC tables
  01_persona_groups.sql   notes for the persona groups
  02_gold_views.sql       the unified gold layer
  03_classification_abac.sql  PII/commercial tags + ABAC column mask
genie/build_genie.py      authors the Genie space
dashboard/build_dashboard.py  builds the Lakeview dashboard
app/
  app.py, server/         FastAPI backend (bookings CRUD, master data, capacity,
                           governance, AI, Genie proxy, architecture stats)
  frontend/               React + Vite + Tailwind UI (ACC-branded)
  deploy_app.py           build + deploy the app, grant the service principal
```

## Customising

- **Different catalog name**: set `ACC_CATALOG`. The deployer rewrites the SQL to
  your catalog at deploy time, so you are not tied to the default name.
- **Scale**: row counts / seed are constants at the top of `data_gen/generate.py`.

## Teardown

```bash
databricks apps stop acc-livestock-planner --profile $ACC_PROFILE   # then delete in the UI
databricks api post /api/2.0/sql/statements --profile $ACC_PROFILE --json \
  '{"warehouse_id": "'"$ACC_WAREHOUSE"'", "statement": "DROP SCHEMA IF EXISTS '"$ACC_CATALOG"'.acc_feedlot CASCADE"}'
# repeat for acc_counterparty, acc_reference, acc_booking, acc_audit, acc_gold
```

Delete the Genie space and dashboard from the workspace UI, and remove the
`acc_*` groups if you created them.

## Notes

This is a demonstration of the platform pattern, not production code. The data is
entirely synthetic; Australian Country Choice, the feedlots, growers, agents and
bookings are all fictional. Foundation model availability and SQL warehouse
channels vary by region and workspace.
