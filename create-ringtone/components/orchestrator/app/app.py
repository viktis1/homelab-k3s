import os
import uuid

from fastapi import BackgroundTasks, FastAPI, HTTPException, APIRouter, Depends
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, UUID4
from typing import Literal
from datetime import datetime
from contextlib import asynccontextmanager
from textwrap import dedent # for fastAPI formatting of multi-line strings
import firebase_admin
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


from database import init_db, create_job, set_job, get_job, return_voice
from main import (
    create_ringtone,
    get_object_bytes,
    list_available_voices,
    get_reference_audio_stream,
    PUBLIC_VOICE_PREFIX
)



@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db() # Before the app starts
    yield # This is where the app runs
    # Nothing happens on app shutdown, since I am not using a database connection pool.

app = FastAPI(
    lifespan=lifespan,
    title="Create Ringtone API",
    description="""
Generate personalized ringtones using text-to-speech.

## Workflow

1. `GET /voices` — Retrieve available voices and clips.
2. `GET /voice-preview` — Preview a selected voice clip.
3. `POST /generate` — Submit a ringtone generation job.
4. `GET /status/{job_id}` — Monitor generation progress.
5. `GET /download/{job_id}` — Download the completed WAV file.

Generation is asynchronous. Jobs transition through
`queued`, `running`, and either `done` or `failed`.

A client may provide its own UUID4 job ID to prevent duplicate submissions.
""",
)

class CreateRingtoneRequest(BaseModel): # the following is nice for docs
    receiver: str = Field(
        min_length=1,
        description="Name of the person receiving the call.",
        examples=["Viktor"],
    )
    caller: str = Field(
        min_length=1,
        description="Name of the person calling.",
        examples=["John"],
    )
    voice_id: str = Field(
        min_length=1,
        description="Voice ID returned by GET /voices.",
        examples=["seth_rogan"],
    )
    clip_id: str = Field(
        min_length=1,
        description="Clip ID returned by GET /voices.",
        examples=["clip1.wav"],
    )
    job_id: UUID4 | None = Field(
        default=None,
        description="Optional UUID4. Reusing an existing ID returns the existing job.",
    )

# create a way to authenticate users with firebase.
firebase_admin.initialize_app(
    options={"projectId": os.environ["FIREBASE_PROJECT_ID"]}
)
security = HTTPBearer()
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    try:
        decoded = firebase_admin.auth.verify_id_token(credentials.credentials)
        return decoded["uid"]
    except firebase_admin.auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token expired")
    except (firebase_admin.auth.InvalidIdTokenError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid Firebase token")
    except firebase_admin.auth.CertificateFetchError:
        raise HTTPException(status_code=503, detail="Authentication unavailable")
router = APIRouter(Depends(get_current_user)) # Use router for endpoints that require authentication


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@router.post(
    "/generate",
    status_code=202,
    summary="Submit a ringtone generation job",
    description=dedent("""
    If a job ID already exists, the original job is returned, even 
    if the new request contains different parameters.

    **Response (HTTP 202):**

    ```json
    {
      "job_id": "32-character hexadecimal UUID",
      "status": "queued",
      "status_url": "/status/<job_id>",
      "download_url": "/download/<job_id>"
    }
    ```

    The status may also be `running`, `done`, or `failed` when an existing 
    job ID is supplied. Please use the `status_url` and `download_url` to 
    check check if the job is complete and to download the generated ringtone.
    """),
)
def generate(request: CreateRingtoneRequest, background_tasks: BackgroundTasks):
    job_id = request.job_id.hex if request.job_id else uuid.uuid4().hex
    voice_clip_path = f"{PUBLIC_VOICE_PREFIX}{request.voice_id}/{request.clip_id}"

    created = create_job(
        job_id,
        {
            "status": "queued",
            "receiver": request.receiver,
            "caller": request.caller,
            "voice_clip_path": voice_clip_path,
        },
    )
    if created:
        background_tasks.add_task(
            create_ringtone,
            job_id,
            request.receiver,
            request.caller,
            voice_clip_path,
        )

    return {
        "job_id": job_id,
        "status": "queued" if created else get_job(job_id)["status"],
        "status_url": f"/status/{job_id}",
        "download_url": f"/download/{job_id}",
    }

@router.get(
    "/status/{job_id}",
    summary="Get ringtone generation status",
    description=dedent("""
    Retrieve the current job status and available metadata.

    **statuses:** 
    - `queued`: Waiting to start. Only one job at a time.
    - `running`: Ringtone generation is in progress.
    - `done`: The ringtone is ready. Use /download/{job_id} to retrieve it.
    - `failed`: Generation failed. The `error` field describes the problem.

    
    
    Additional fields are included as generation progresses.
    Failed jobs include the error message in `error`.
    """),
)
def status(job_id: str):
    job = get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )
    return job

@router.get(
    "/voices",
    summary="List available voices and their associated audio clips",
    description=dedent("""
    Returns a JSON object containing a `voices` array.
    Each voice has an `id`, `name`, and `clips` array.
    Each clip has an `id` and `name`.

    Use the returned IDs with `/voice-preview` and `/generate`.
    """),
)
def voices():
    return {
        "voices": list_available_voices(),
    }

@router.get(
    "/voice-preview",
    summary="Preview a voice clip",
    description=dedent("""
    Use `voice_id` and `clip_id` values returned by `GET /voices`.
    Returns WAV or MP3 audio depending on the clip format.
    """),
    responses={
        200: {
            "description": "Reference audio stream.",
            "content": {
                "audio/wav": {},
                "audio/mpeg": {},
            },
        },
    },
)
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

@router.get(
    "/download/{job_id}",
    summary="Download a completed ringtone",
    description=dedent("""
    The job must have reached `done` status before downloading.

    succesful responses returns the WAV file (`audio/wav`).
    """),
)
def download(job_id: str):
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


@router.get(
    "/check-upload/{voice_uuid}",
    summary="Check if a voice upload has gone through on the server",
    description=dedent("""
    When uploading a voice recording, the client uploads to GCP and then the server copies it to RustFS and registers it in PostgreSQL.
    To check if the upload has been registered, call this endpoint with the UUID (clint generates the UUID) of the voice recording.

    Returns a boolean indicating whether the voice upload exists in the database.
    """),
)
def get_recording(voice_uuid: str):
    try:
        recording = return_voice(voice_uuid)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid UUID"
        )

    if recording is None:
        raise HTTPException(
            status_code=404,
            detail="Recording not found"
        )

    return recording

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/", include_in_schema=False)
def index():
    return FileResponse("static/index.html")

app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        reload=False,
    )
