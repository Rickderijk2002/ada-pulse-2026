from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import uuid

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.cloud import pubsub_v1
from google.genai import types as genai_types
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# SQLite file for ADK session state (ADK web UI only)
SESSION_DB_URL = f"sqlite:///{os.path.join(BASE_DIR, 'sessions.db')}"

# Build the ADK-powered FastAPI app.
# agents_dir points to this folder - ADK discovers pulse_oi/agent.py automatically.
# web=True enables the ADK web UI at http://localhost:8081 for local testing.
app: FastAPI = get_fast_api_app(
    agents_dir=BASE_DIR,
    session_service_uri=SESSION_DB_URL,
    allow_origins=["*"],
    web=True,
)

# Programmatic pipeline runner
# Separate from the ADK web UI - uses its own in-memory session service.
# Each /pipeline/run call gets a fresh isolated session.

APP_NAME = "OperationalIntelligencePipeline"
_session_service = InMemorySessionService()

# Pub/Sub config - read from .env
GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
INSIGHTS_READY_TOPIC = os.getenv("INSIGHTS_READY_TOPIC", "insights-ready")


def _publish_insights_ready(run_id: str, tenant_id: str, insights: dict) -> None:
    """
    Publish the synthesized insights to the insights-ready Pub/Sub topic.
    Skipped silently if GOOGLE_CLOUD_PROJECT is not set (e.g. offline dev).
    """
    if not GCP_PROJECT:
        logger.info("GOOGLE_CLOUD_PROJECT not set - skipping Pub/Sub publish")
        return

    topic_path = f"projects/{GCP_PROJECT}/topics/{INSIGHTS_READY_TOPIC}"
    payload = json.dumps({
        "run_id": run_id,
        "tenant_id": tenant_id,
        "final_severity": insights.get("final_severity", "unknown"),
        "insights": insights,
    }).encode("utf-8")

    try:
        publisher = pubsub_v1.PublisherClient()
        future = publisher.publish(topic_path, payload)
        message_id = future.result(timeout=10)
        logger.info("Published insights-ready - message_id=%s topic=%s", message_id, topic_path)
    except Exception as exc:
        # Log but do not crash the pipeline - publishing is best-effort
        logger.error("Failed to publish insights-ready: %s", exc)


PIPELINE_PROMPT = (
    "Run the full Pulse Operational Intelligence pipeline for tenant pulse-demo. "
    "Analyse all financial and sales CRM KPIs, detect risks and trends, "
    "and return the consolidated intelligence report as raw JSON only."
)


async def _run_pipeline(tenant_id: str, run_id: str) -> dict:
    """
    Programmatically run the full OI pipeline for a given tenant.
    Returns the parsed synthesized_insights dict.
    """
    # Imported inside function to avoid circular imports at module load time
    from pulse_oi.agent import root_agent  # noqa: PLC0415

    # Fresh session for this run
    session = await _session_service.create_session(
        app_name=APP_NAME,
        user_id="system",
        session_id=run_id,
    )

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=_session_service,
    )

    message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=PIPELINE_PROMPT)],
    )

    # Run pipeline to completion - consume all events
    async for _event in runner.run_async(
        user_id="system",
        session_id=session.id,
        new_message=message,
    ):
        pass

    # Read final output from session state
    completed = await _session_service.get_session(
        app_name=APP_NAME,
        user_id="system",
        session_id=run_id,
    )

    raw = completed.state.get("synthesized_insights", "{}")

    # Strip markdown code fences if the model added them despite instructions
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("synthesized_insights is not valid JSON: %s", raw[:200])
            raise HTTPException(status_code=502, detail="Pipeline returned invalid JSON")
    else:
        result = raw if isinstance(raw, dict) else {}

    # Step 5 - publish synthesized insights to insights-ready topic
    _publish_insights_ready(run_id=run_id, tenant_id=tenant_id, insights=result)

    return result


# Request / response models

class PipelineRunRequest(BaseModel):
    tenant_id: str = "pulse-demo"
    run_id: str | None = None


class PubSubBody(BaseModel):
    message: dict
    subscription: str | None = None


# Endpoints

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "operational-intelligence-orchestrator"}


@app.post("/pipeline/run")
async def pipeline_run(req: PipelineRunRequest) -> dict:
    """
    Manually trigger the full OI pipeline.
    Returns the synthesized_insights payload when complete.

    PowerShell example:
        $body = @{tenant_id="pulse-demo"; run_id="manual-001"} | ConvertTo-Json
        Invoke-RestMethod -Method Post -Uri http://localhost:8081/pipeline/run
            -ContentType "application/json" -Body $body
    """
    run_id = req.run_id or str(uuid.uuid4())
    logger.info("Pipeline run started - run_id=%s tenant=%s", run_id, req.tenant_id)

    result = await _run_pipeline(req.tenant_id, run_id)

    logger.info("Pipeline run completed - run_id=%s severity=%s",
                run_id, result.get("final_severity", "unknown"))

    return {"run_id": run_id, "status": "completed", "result": result}


@app.post("/pubsub/kpis-computed", status_code=200)
async def pubsub_kpis_computed(body: PubSubBody) -> dict:
    """
    Pub/Sub push handler - called by GCP when kpis-computed topic fires.
    Decodes the base64 payload, extracts tenant_id and run_id, fires pipeline.
    Returns 200 immediately so Pub/Sub does not retry.
    Pipeline runs in the background via asyncio.create_task.
    """
    try:
        raw_data = base64.b64decode(body.message.get("data", "")).decode("utf-8")
        payload = json.loads(raw_data)
    except Exception:
        payload = {}

    tenant_id = payload.get("tenant_id", "pulse-demo")
    run_id = payload.get("run_id") or str(uuid.uuid4())

    logger.info("Pub/Sub trigger received - run_id=%s tenant=%s", run_id, tenant_id)

    # Fire and forget - Pub/Sub needs a fast 200, pipeline runs in background
    asyncio.create_task(_run_pipeline(tenant_id, run_id))

    return {"status": "accepted", "run_id": run_id}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081, reload=False)
