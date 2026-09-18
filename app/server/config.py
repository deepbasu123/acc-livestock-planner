"""Dual-mode auth + shared config for the ACC Livestock Planner app."""
import os
from functools import lru_cache
from databricks.sdk import WorkspaceClient

IS_APP = bool(os.environ.get("DATABRICKS_APP_NAME"))

CATALOG = os.environ.get("ACC_CATALOG", "deep_test_1_catalog")
WAREHOUSE_ID = os.environ.get("ACC_WAREHOUSE", "")
GENIE_SPACE_ID = os.environ.get("ACC_GENIE_SPACE", "")
DASHBOARD_ID = os.environ.get("ACC_DASHBOARD", "")
LLM_MODEL = os.environ.get("ACC_LLM_MODEL", "databricks-claude-sonnet-4-6")


@lru_cache(maxsize=1)
def get_client() -> WorkspaceClient:
    if IS_APP:
        return WorkspaceClient()
    profile = os.environ.get("DATABRICKS_PROFILE", "deep-test-1")
    return WorkspaceClient(profile=profile)


def get_host() -> str:
    if IS_APP:
        host = os.environ.get("DATABRICKS_HOST", "")
        if host and not host.startswith("http"):
            host = f"https://{host}"
        return host
    return get_client().config.host


def get_token() -> str:
    headers = get_client().config.authenticate()
    if headers and "Authorization" in headers:
        return headers["Authorization"].replace("Bearer ", "")
    return os.environ.get("DATABRICKS_TOKEN", "")
