"""Lodestar FastAPI app (Layer 5 backend).

Serves the precomputed ranked store and the on-demand trajectory task.

    uv run uvicorn backend.api.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import asteroids, trajectory

app = FastAPI(title="Lodestar PAC", version="0.1.0")

# Dev CORS: allow the Vite dev server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(asteroids.router, prefix="/api")
app.include_router(trajectory.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
