from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from email_sender import send
from renderer import render

HERE = Path(__file__).parent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Pulse Reporting Delivery", version="0.1.0")


class PubSubBody(BaseModel):
    message: dict
    subscription: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/pubsub/insights-ready")
def pubsub_insights_ready(body: PubSubBody) -> dict:
    try:
        raw = base64.b64decode(body.message.get("data", "")).decode("utf-8")
        payload = json.loads(raw)
    except Exception as exc:
        logger.error("Failed to decode Pub/Sub message: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid Pub/Sub message") from exc

    insight_path = HERE / "received_insight.json"
    insight_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Saved insight payload to %s", insight_path)

    render(insight_path, HERE / "report.html")
    send()

    return {"status": "ok"}


@app.post("/test")
def test_endpoint(payload: dict) -> dict:
    insight_path = HERE / "received_insight.json"
    insight_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Saved test payload to %s", insight_path)

    render(insight_path, HERE / "report.html")
    send()

    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8082)
