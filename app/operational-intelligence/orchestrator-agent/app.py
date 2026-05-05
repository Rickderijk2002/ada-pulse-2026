from __future__ import annotations

import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# SQLite file for ADK session state (local only)
SESSION_DB_URL = f"sqlite:///{os.path.join(BASE_DIR, 'sessions.db')}"

# Build the ADK-powered FastAPI app.
# agents_dir points to this folder — ADK discovers pulse_oi/agent.py automatically.
# web=True enables the ADK web UI at http://localhost:8081 for local testing.
app: FastAPI = get_fast_api_app(
    agents_dir=BASE_DIR,
    session_service_uri=SESSION_DB_URL,
    allow_origins=["*"],
    web=True,
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "operational-intelligence-orchestrator"}


# ── NOTE FOR RICK ─────────────────────────────────────────────────────────────
# The Pub/Sub push handler (POST /pubsub/kpis-computed) and the manual
# trigger endpoint (POST /pipeline/run) will be added here in Step 4.
# For now, use the ADK web UI at http://localhost:8081 to run and test the
# full agent pipeline interactively.
# ─────────────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081, reload=False)
