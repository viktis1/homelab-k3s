import os
import threading
import uuid

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
    

from main import (
    create_ringtone,
    get_object_bytes,
    list_available_voices,
    get_reference_audio_stream,
    PUBLIC_VOICE_PREFIX
)


app = FastAPI()

class CreateRingtoneRequest(BaseModel):
    receiver: str = Field(min_length=1)
    caller: str = Field(min_length=1)
    voice_id: str = Field(min_length=1)
    clip_id: str = Field(min_length=1)

# ---------------------------------------------------------------------------
# Create a dict to store job status.
# ---------------------------------------------------------------------------
# Limitation:
# - jobs disappear if this pod restarts... Might need a persistent store...

jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()


def set_job(job_id: str, value: dict) -> None:
    with jobs_lock:
        jobs[job_id] = value


def get_job(job_id: str) -> dict | None:
    with jobs_lock:
        job = jobs.get(job_id)
        return dict(job) if job is not None else None


# ---------------------------------------------------------------------------
# Background pipeline execution
# ---------------------------------------------------------------------------
def run_ringtone_job(job_id: str, request: CreateRingtoneRequest, voice_clip_path: str) -> None:
    set_job(job_id, {"status": "running"})

    try:
        tts_job, output_key, script = create_ringtone(
            receiver=request.receiver,
            caller=request.caller,
            voice_clip_path=voice_clip_path,
        )
        set_job(
            job_id,
            {
                "status": "done",
                "tts_job": tts_job,
                "output_key": output_key,
                "script": script,
            },
        )
    except Exception as exc:
        set_job(job_id,{"status":"failed", "error": str(exc)})


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@app.post("/generate", status_code=202)
def generate(request: CreateRingtoneRequest, background_tasks: BackgroundTasks):
    """
    Start ringtone creation and immediately return an API job ID.
    This creates a background task, so it is important to lock threads
    when getting and setting jobs.
    """
    job_id = uuid.uuid4().hex

    voice_clip_path = f"{PUBLIC_VOICE_PREFIX}{request.voice_id}/{request.clip_id}"

    set_job(
        job_id,
        {
            "status": "queued",
        },
    )
    background_tasks.add_task(
        run_ringtone_job,
        job_id,
        request,
        voice_clip_path,
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "status_url": f"/status/{job_id}",
        "download_url": f"/download/{job_id}",
    }


@app.get("/status/{job_id}")
def status(job_id: str):
    job = get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )
    return job

@app.get("/voices")
def voices():
    return {
        "voices": list_available_voices(),
    }

@app.get("/voice-preview")
def voice_preview(voice_id: str, clip_id: str):

    voice_clip_path = f"{PUBLIC_VOICE_PREFIX}{voice_id}/{clip_id}"

    audio = get_reference_audio_stream(voice_clip_path)

    if clip_id.lower().endswith(".mp3"):
        media_type = "audio/mpeg"
    else:
        media_type = "audio/wav"

    return StreamingResponse(
        audio.iter_chunks(chunk_size=64 * 1024),
        media_type=media_type,
    )

@app.get("/download/{job_id}")
def download(job_id: str):
    """
    Download a completed ringtone through the API.
    """
    job = get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )
    if job["status"] != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Job is not complete. Current status: {job['status']}",
        )

    wav_bytes = get_object_bytes(job["output_key"])
    filename = job["output_key"].split("/")[-1]

    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def index():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        reload=False,
    )
