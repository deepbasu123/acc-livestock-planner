# ACC Livestock Procurement Planner

A Databricks demo built for **Australian Country Choice (ACC)** - a 100% Australian,
family-owned, vertically integrated beef supply chain business. It reproduces the
functionality of ACC's real cattle-booking prototype (a Postgres-backed app) as a native
**Databricks App** (React + FastAPI) on top of **Lakebase** (managed Postgres) and
**Unity Catalog**, with the platform's own governance, natural-language and analytics
layers added on top.

Everything is synthetic and generated from a seeded script - there is no real ACC
data anywhere in this repo. You deploy it into your own workspace with one command.

## What it does

Replaces the per-feedlot Excel spreadsheets ACC's procurement team used to plan
cattle bookings into three feedlots - **BPFL** (Brindley Park), **Opal Ck** (Opal
Creek) and **BVFL** (Burnett Valley):

- **Dashboard** - total bookings, total head count, head count per feedlot, and
  three "+ New <Feedlot> Booking" shortcuts that deep-link into a pre-filled form.
- **Bookings** - search, filter (feedlot / status / week / buyer / agent / origin),
  and one-click Excel export of the filtered list with every foreign key resolved
  to a name.
- **Booking detail** - view/edit, **Duplicate** (copies the booking, resets status
  to Draft), soft **Delete** (never hard-deleted), and a full **change history**
  (a log of create/update/delete/duplicate events with old + new values, written
  by the app on every mutation; nothing in the UI ever issues an `UPDATE` or
  `DELETE` against it).
- **Master Data** - manage the seven dropdown lists used on the booking form
  (Agents, Vendor Properties, Payees, Programs, Weigh Points, Origins, Buyers):
  add, rename, activate/deactivate, delete.

## What's added for the Databricks demo

The reference app is deliberately a simple booking CRUD tool (its own spec calls
out "no KPIs, analytics, charts, or executive dashboards"). On top of that exact
functionality, this rebuild adds the platform capabilities a customer conversation
usually wants to see, cleanly separated into their own tabs so the core workflow
stays uncluttered:

- **Capacity Forecast** - feedlot utilisation estimated from booked head count
  against pen capacity, plus a market price trend, with an AI-generated capacity
  strategy (Foundation Model API).
- **Governance** - Unity Catalog ABAC column masking on commercial pricing fields
  (`price_per_kg`, `price_variation`, `buyer_payee_details`), switchable live by
  persona (Executive / Procurement / Operations).
- **Ask ACC** - an embedded AI/BI Genie space for natural-language questions across
  the booking model.
- **Architecture** - a reference-architecture diagram, the masking policy table,
  and live deployed-object counts pulled from `information_schema`.

## Architecture: Lakebase edition

This demo splits the workload:

- **Operational data (OLTP)**: The cattle bookings, seven master-data lists, and audit
  log live in Lakebase (managed Postgres) as the system of record. Every read and write
  is a low-latency Postgres round-trip handled by the FastAPI backend (server/pg.py).
  The app's service principal mints short-lived OAuth database credentials and refreshes
  them on a background thread. On startup, the backend creates its own Postgres schema,
  tables, "gold" views, and self-seeds them from shipped JSONL (server/pg_bootstrap.py).

- **Analytics & governance (OLAP)**: The Capacity Forecast and Governance tabs read
  the Postgres gold views directly. The AI/BI dashboard, Genie space, and Unity Catalog
  ABAC column-masking are built on Delta tables in UC from the same synthetic data, so
  those queries run in parallel without contention.

The /api contract (frontend to backend) is unchanged from the original, so the React UI
works identically.

## Data model

Operational data in Lakebase (Postgres):

```
public.feedlots           feedlots (capacity/location)
public.counterparties     agents, vendors, payees, buyers
public.reference_data     programs, weigh_points, origins
public.bookings           cattle_bookings - the hero table
public.booking_history    audit log (app-only INSERTs)
public.gold.*             computed views for frontend queries
```

Analytics data in Unity Catalog (Delta):

```
acc_feedlot       feedlots snapshot
acc_counterparty  agents, vendors, payees, buyers snapshot
acc_reference     programs, weigh_points, origins snapshot
acc_booking       cattle_bookings snapshot
acc_audit         booking_history snapshot
acc_gold          booking_expanded (every FK resolved to a name) + supporting
                  views: feedlot_capacity_weekly, vendor_scorecard,
                  agent_performance, price_trend_weekly
```

`cattle_bookings` matches the reference schema field-for-field, including its
deliberately loose text fields (`price_per_kg`, `grid_text`, `week_number`) that
field staff fill in with real-world formats rather than a strict numeric type.
The gold view parses a best-effort numeric price (`price_per_kg_numeric`) for
aggregation without changing the source column.

## Prerequisites

- A Databricks workspace with Unity Catalog and a SQL warehouse (Serverless or Pro).
- Permission to create a Lakebase project (or permission to connect to an existing one).
- The [Databricks CLI](https://docs.databricks.com/dev-tools/cli/index.html) installed
  and on PATH.
- Python 3.10+ (`pip install -r requirements.txt`).
- Node 18+ (only needed for `--with-app`, to build the React frontend).
- Permission to create (or write to) a catalog. Many shared/FE-VM workspaces have
  no default storage root configured for `CREATE CATALOG`; point `ACC_CATALOG` at
  an existing catalog instead - every schema here is prefixed `acc_` so it won't
  collide with anything else already in that catalog.

## Quick start

```bash
git clone <this-repo>
cd acc-livestock-planner
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. configure for your workspace
cp config.example.sh config.sh
$EDITOR config.sh                       # set profile, host, warehouse, catalog,
                                        # lakebase project, postgres schema, llm model
source config.sh

# 2. authenticate the CLI (if you haven't)
databricks auth login --profile $ACC_PROFILE

# 3. deploy the data + analytics layer (Delta, gold views, Genie, dashboard)
python3 deploy.py

# 4. provision the Lakebase project + deploy the app
python3 deploy.py --with-app
```

`deploy.py` runs these phases in order and is safe to re-run:

| Phase | What it does |
|---|---|
| provision | creates the catalog (if it can) and the six UC schemas |
| data | generates the synthetic data, uploads it, loads each UC table |
| gold | builds the gold views, applies the commercial-pricing ABAC mask |
| lakebase | provisions or discovers the Lakebase project, validates connectivity |
| genie | creates the Genie space and prints its id |
| dashboard | creates the AI/BI dashboard and prints its id |
| app | (with `--with-app`) builds the frontend, deploys the app, grants its service principal access, creates the Postgres schema in Lakebase |

All workspace-specific IDs (catalog, warehouse, Genie space, dashboard, app) are
discovered or created at deploy time and wired into the configuration. Nothing
workspace-specific is hard-coded. Synthetic data is generated fresh on each deploy.

Run a single phase with `python3 deploy.py --only data`.

## config.sh

Edit this file with your workspace details:

```bash
ACC_PROFILE=<your-cli-profile>          # Databricks CLI profile
ACC_HOST=<workspace-url>                # https://...
ACC_WAREHOUSE=<warehouse-id>            # SQL warehouse for analytics queries
ACC_CATALOG=<catalog-name>              # Unity Catalog (create or existing)
ACC_APP_NAME=acc-livestock-planner      # Databricks App name (choose one)
ACC_LAKEBASE_PROJECT=<project-name>     # Lakebase project (will be created)
ACC_PG_SCHEMA=acc_operational           # Postgres schema name
ACC_LLM_MODEL=meta-llama-3-1-70b        # Foundation model for AI features
```

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
different columns live - the masking is enforced in Unity Catalog, so it applies
identically to the app, the dashboard, Genie and raw SQL.

## Repo layout

```
deploy.py                 one-command orchestrator
config.example.sh         deployment configuration (copy to config.sh)
data_gen/generate.py       seeded generator for the five UC source systems
sql/
  dbsql.py                SQL Statements API helper
  load_tables.py          load staged parquet into UC tables
  01_persona_groups.sql   notes for the persona groups
  02_gold_views.sql       the unified analytics gold layer
  03_classification_abac.sql  PII/commercial tags + ABAC column mask
genie/build_genie.py      authors the Genie space
dashboard/build_dashboard.py  builds the AI/BI dashboard
app/
  app.py, server/         FastAPI backend (bookings CRUD, master data, capacity,
                           governance, AI, Genie proxy, architecture stats)
                           + server/pg.py (Lakebase connection pool)
                           + server/pg_bootstrap.py (schema bootstrap)
  frontend/               React + Vite + Tailwind UI (ACC-branded)
  deploy_app.py           build + deploy the app, grant the service principal,
                           wire the postgres resource
```

## Customising

- **Different catalog name**: set `ACC_CATALOG`. The deployer rewrites the SQL to
  your catalog at deploy time, so you are not tied to the default name.
- **Different Lakebase project**: set `ACC_LAKEBASE_PROJECT`. If the project exists,
  it will be reused; if not, it will be created.
- **Scale**: row counts / seed are constants at the top of `data_gen/generate.py`.

## Teardown

```bash
databricks apps stop $ACC_APP_NAME --profile $ACC_PROFILE   # then delete in the UI

# Drop the UC schemas
databricks api post /api/2.0/sql/statements --profile $ACC_PROFILE --json \
  '{"warehouse_id": "'"$ACC_WAREHOUSE"'", "statement": "DROP SCHEMA IF EXISTS '"$ACC_CATALOG"'.acc_feedlot CASCADE"}'
# repeat for acc_counterparty, acc_reference, acc_booking, acc_audit, acc_gold

# Delete the Genie space and dashboard from the workspace UI

# Delete the Lakebase project from the workspace UI

# Remove the workspace groups
databricks groups delete --display-name acc_exec --profile $ACC_PROFILE
databricks groups delete --display-name acc_procurement --profile $ACC_PROFILE
databricks groups delete --display-name acc_operations --profile $ACC_PROFILE
```

## Notes

This is a demonstration of the platform pattern, not production code. The data is
entirely synthetic; Australian Country Choice, the feedlots, growers, agents and
bookings are all fictional. Foundation model availability and SQL warehouse
channels vary by region and workspace.
