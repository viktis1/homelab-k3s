from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Request as FastAPIRequest
from fastapi.responses import FileResponse
from kubernetes import client
from pydantic import BaseModel


router = APIRouter()

JOB_TYPE = "tts"
NAMESPACE = "tts"

RESULT_DIR = Path("/results")


class Request(BaseModel):
    prompt: str = ("This is a sentence read out loud by a text-to-speech model."
    )


def build_job(
    core_api: client.CoreV1Api,
    request: Request,
    job_name: str,
):
    # Get the Job template from the TTS namespace
    config_map = core_api.read_namespaced_config_map(
        name="tts-job-template",
        namespace=NAMESPACE,
    )

    job = yaml.safe_load(
        config_map.data["tts.job.yaml"]
    )

    callback_url = (
        "http://gpu-orchestrator.gpu-orchestrator.svc.viktor.cluster:8000"
        f"/internal/jobs/tts/{job_name}/result"
    )


    # Find the TTS container
    container = next(
        container
        for container in job["spec"]["template"]["spec"]["containers"]
        if container.get("name") == "tts"
    )
    # Values that should change for this particular Job
    env_overrides = {
        "TTS_TEXT": request.prompt,
        "OUTPUT_FILE": f"/tts-data/models/output/{job_name}.wav",
        "REQUEST_ID": job_name,
        "CALLBACK_URL": callback_url,
    }
    # Update existing env vars without replacing the entire env list
    for env in container.get("env", []):
        if env["name"] in env_overrides:
            env["value"] = env_overrides.pop(env["name"])
    # Add any variables that weren't already defined in the template
    for name, value in env_overrides.items():
        container.setdefault("env", []).append({
            "name": name,
            "value": value,
        })
    return job


def read_result(
    core_api: client.CoreV1Api,
    pod: client.V1Pod,
    job_name: str,
):
    result_path = RESULT_DIR / f"{job_name}.wav"

    return FileResponse(
        path=result_path,
        media_type="audio/wav",
        filename=f"{job_name}.wav",
    )


# --------------------------------------------------------------------------
# Callback endpoint
# --------------------------------------------------------------------------

@router.post("/internal/jobs/tts/{job_name}/result", status_code=201)
async def receive_result(
    job_name: str,
    request: FastAPIRequest,
):
    wav_bytes = await request.body()

    if not wav_bytes:
        raise HTTPException(
            status_code=400,
            detail="No audio data received.",
        )

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    result_path = RESULT_DIR / f"{job_name}.wav"
    result_path.write_bytes(wav_bytes)

    return {
        "job": job_name,
        "status": "received",
    }
