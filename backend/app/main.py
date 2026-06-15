"""FastAPI application entrypoint.

Wires up CORS, mounts each feature router, and starts/stops the background
checkpoint scheduler with the app lifecycle.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, billing, dashboard, ingest, orbs, reports
from app.scheduler import shutdown_scheduler, start_scheduler

app = FastAPI(title="Orbs MVP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(ingest.router)
app.include_router(billing.router)
app.include_router(orbs.router)
app.include_router(dashboard.router)
app.include_router(reports.router)
app.include_router(auth.router)


@app.on_event("startup")
async def startup() -> None:
    # No-op unless ENABLE_CHECKPOINT_SCHEDULER is set (see app/config.py).
    start_scheduler()


@app.on_event("shutdown")
async def shutdown() -> None:
    shutdown_scheduler()
