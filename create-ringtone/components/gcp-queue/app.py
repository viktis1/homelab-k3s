"""Tiny HTTP endpoint that publishes ringtone requests to Pub/Sub."""

import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import FastAPI, Header, HTTPException
from google.cloud import pubsub_v1
from pydantic import BaseModel, Field

app = FastAPI()


class RingtoneRequest(BaseModel):
    receiver: str = Field(min_length=1)
    caller: str = Field(min_length=1)
    voice_id: str = Field(min_length=1)
    clip_id: str = Field(min_length=1)


@lru_cache(maxsize=1)
def publisher():
    return pubsub_v1.PublisherClient()


@app.post("/enqueue", status_code=202)
def enqueue(request: RingtoneRequest, x_api_key: str = Header(default="")):
    if not hmac.compare_digest(x_api_key, os.environ["ENQUEUE_API_KEY"]):
        raise HTTPException(status_code=401, detail="Unauthorized")

    job_id = uuid.uuid4().hex
    submitted_at = datetime.now(timezone.utc).isoformat()
    message = {
        "job_id": job_id,
        "submitted_at": submitted_at,
        "request": request.model_dump(),
    }

    # Waiting for the publish result means HTTP 202 signifies Pub/Sub accepted it.
    try:
        publisher().publish(
            os.environ["PUBSUB_TOPIC"], json.dumps(message).encode("utf-8")
        ).result(timeout=15)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not publish request") from exc

    return {"job_id": job_id, "status": "queued", "submitted_at": submitted_at}
