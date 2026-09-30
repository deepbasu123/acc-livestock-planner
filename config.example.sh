# ACC Livestock Planner - deployment configuration.
# Copy to config.sh, fill in for YOUR workspace, then:  source config.sh
# (config.sh is gitignored so your IDs never get committed.)

# Databricks CLI profile to use (must be authenticated: `databricks auth login --profile ...`)
export ACC_PROFILE="DEFAULT"

# Workspace URL (used by the SQL Statements API helper)
export ACC_HOST="https://<your-workspace>.cloud.databricks.com"

# SQL warehouse id (Databricks SQL -> Warehouses -> your warehouse -> copy the ID).
# A Serverless or Pro warehouse is recommended.
export ACC_WAREHOUSE="<your-warehouse-id>"

# Unity Catalog catalog to deploy into. The deployer will CREATE IF NOT EXISTS;
# if you lack CREATE CATALOG on the metastore (common on shared/FE-VM workspaces
# with no default storage root configured), point this at the workspace's
# existing catalog instead - all six schemas below are prefixed "acc_" so they
# won't collide with any other demo sharing that catalog.
export ACC_CATALOG="main"

# Workspace folder the Genie space, dashboard and app source live under.
export ACC_PARENT="/Workspace/Shared/acc-livestock-planner"

# Foundation model for the app's AI summaries (Databricks Model Serving name).
export ACC_LLM_MODEL="databricks-claude-sonnet-4-6"

# Databricks App name (lowercase letters/numbers/hyphens, <= 26 chars).
export ACC_APP_NAME="acc-livestock-planner"

# --- Lakebase (operational Postgres) ---
# Lakebase Autoscaling project that backs the app's operational data. deploy.py
# creates it if it doesn't exist (or reuses it), then attaches it to the app.
# Id: lowercase letters/numbers/hyphens, must start with a letter.
export ACC_LAKEBASE_PROJECT="acc-livestock-planner"
# Postgres schema the app owns (its service principal creates + seeds it).
export ACC_PG_SCHEMA="acc"

# Filled in automatically by deploy.py; only set these if deploying the app on its own.
# export ACC_GENIE_SPACE="<genie-space-id>"
# export ACC_DASHBOARD="<dashboard-id>"
