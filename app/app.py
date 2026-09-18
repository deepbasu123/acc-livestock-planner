"""ACC Livestock Planner - FastAPI entry point."""
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from server.config import get_host, GENIE_SPACE_ID, DASHBOARD_ID, CATALOG
from server.routes import bookings, masterdata, governance, ai, genie_chat, capacity, architecture

app = FastAPI(title="ACC Livestock Planner")

app.include_router(bookings.router, prefix="/api")
app.include_router(masterdata.router, prefix="/api")
app.include_router(governance.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(genie_chat.router, prefix="/api")
app.include_router(capacity.router, prefix="/api")
app.include_router(architecture.router, prefix="/api")


@app.get("/api/config")
def config():
    host = get_host()
    return {
        "genie_space_id": GENIE_SPACE_ID,
        "genie_url": f"{host}/genie/rooms/{GENIE_SPACE_ID}",
        "dashboard_url": f"{host}/dashboardsv3/{DASHBOARD_ID}/published",
        "catalog": CATALOG,
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---- serve React frontend ----
FRONTEND = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(FRONTEND):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        idx = os.path.join(FRONTEND, "index.html")
        if os.path.exists(idx):
            return FileResponse(idx)
        return JSONResponse({"error": "frontend not built"}, status_code=404)
