import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath

import boto3
import requests
from botocore.config import Config
from botocore.exceptions import ClientError

from database import set_job


# RustFS is the local object storage. Voice-upload is the bucket for uploaded reference audio.
RUSTFS_BUCKET_IN = "voice-upload"
RUSTFS_BUCKET_OUT = "created-ringtones"
# This is the enpoint for a signed URL the TTS model will use for reference audio.
RUSTFS_ENDPOINT = "http://rustfs.create-ringtone.svc.viktor.cluster:9000"
# Get an access key and secret since I will be accessing RustFS from this pod. Both reading and writing.
RUSTFS_ACCESS_KEY = os.environ["RUSTFS_ACCESS_KEY"]
RUSTFS_SECRET_KEY = os.environ["RUSTFS_SECRET_KEY"]
GPU_ORCHESTRATOR_URL = "http://gpu-orchestrator.gpu-orchestrator.svc.viktor.cluster:8000"
# Prefix for public voices in RustFS.
PUBLIC_VOICE_PREFIX = "famous_people/"
AUDIO_EXTENSIONS = {".wav", ".mp3"}


# Create a S3 client for RustFS
s3 = boto3.client(
    "s3",
    endpoint_url=RUSTFS_ENDPOINT,
    aws_access_key_id=RUSTFS_ACCESS_KEY,
    aws_secret_access_key=RUSTFS_SECRET_KEY,
    region_name="us-east-1", # this is just silly RustFS requirement. It is obviously not true... (local storage)
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
    ),
)

# Ensure that the RustFS Output bucket exists. If it does not exist, create it.
try:
    s3.head_bucket(Bucket=RUSTFS_BUCKET_OUT)
except ClientError as exc:
    status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    if status == 404:
        s3.create_bucket(Bucket=RUSTFS_BUCKET_OUT)
        print(f"Created RustFS bucket: {RUSTFS_BUCKET_OUT}")
    else:
        raise

# ---------------------------------------------------------------------------
# RustFS helpers
# ---------------------------------------------------------------------------
def object_exists(object_key: str) -> bool:
    """Check whether the audio file exists in object storage."""
    try:
        s3.head_object(Bucket=RUSTFS_BUCKET_IN, Key=object_key)
        return True
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status == 404:
            raise FileNotFoundError(f"RustFS object does not exist: s3://{RUSTFS_BUCKET_IN}/{object_key}")
        raise


def create_read_signed_url(
    object_key: str,
    expires_in: int = 1800, # 30 minutes
) -> str:
    """
    Create a short-lived S3 SigV4 GET URL for a RustFS object.
    """
    object_exists(object_key) # Check object exists (we should have already checked though)
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": RUSTFS_BUCKET_IN,
            "Key": object_key,
        },
        ExpiresIn=expires_in,
        HttpMethod="GET",
    )


def save_ringtone(wav_bytes: bytes, caller: str, output_prefix="tester") -> str:
    """Store the finished ringtone in RustFS and return its object key."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
    safe_caller = caller.strip().replace("/", "_") or "unknown"
    output_key = (
        f"{output_prefix}/{safe_caller}/"
        f"ringtone_{timestamp}_{uuid.uuid4().hex[:10]}.wav" # When using 10 hexadecimal characters, there is a 0.005% chance of a collision if you generate 10 000 ringtones at the same time. That is probably ok.
    )
    s3.put_object(
        Bucket=RUSTFS_BUCKET_OUT,
        Key=output_key,
        Body=wav_bytes,
        ContentType="audio/wav",
    )
    return output_key

def get_object_bytes(object_key: str) -> bytes:
    """
    Read an object from RustFS into memory. 
    Used to let end user download finished ringtone...
    """
    return s3.get_object(Bucket=RUSTFS_BUCKET_OUT, Key=object_key)["Body"].read()


# ---------------------------------------------------------------------------
# GPU orchestrator helpers
# ---------------------------------------------------------------------------
def submit_job(job_type: str, prompt: str, reference_audio_url: str | None = None) -> str:
    """
    Submit one TTS Job:
    POST /jobs/tts     {"prompt": "...",  "reference_audio_url": "http://{signed-url}"}
    """
    if job_type == "tts":
        json = {"prompt": prompt, "reference_audio_url": reference_audio_url}
    elif job_type == "llama":
        json = {"prompt": prompt}
    else:
        raise ValueError(f"Unknown job_type: {job_type}")
    response = requests.post(f"{GPU_ORCHESTRATOR_URL}/jobs/{job_type}", json=json, timeout=(10, 120))
    response.raise_for_status()
    payload = response.json()
    job_name = payload.get("job")
    return job_name



def wait_for_result(job_id: str, job_type: str, job_name: str, timeout_seconds: int = 1200):
    """
    Poll gpu-orchestrator until the TTS/LLM Job finishes.
    Store GPU Job status changes in PostgreSQL.

    Current gpu-orchestrator behavior:
    - 202 -> pending/running JSON
    - 200 -> completed WAV bytes
    - 500 -> failed JSON
    """
    result_url = f"{GPU_ORCHESTRATOR_URL}/jobs/{job_type}/{job_name}"
    start_time = time.monotonic()
    deadline = start_time + timeout_seconds
    
    previous_status = None

    while time.monotonic() < deadline:
        response = requests.get(result_url, timeout=(10, 120))

        # Determine GPU Job status
        if response.status_code == 202:
            status = response.json()["status"]
        elif response.status_code == 200:
            status = "completed"
        else:
            status = "failed" if response.status_code == 500 else "unknown"

        # Store status changes and duration on completion
        if status != previous_status:
            set_job(job_id, {
                "status": "running",
                f"{job_type}_status": status,
                **(
                    {f"{job_type}_duration_seconds": round(time.monotonic() - start_time, 2)}
                    if status == "completed" else {}
                ),
            })
            previous_status = status

        # Handle result
        if response.status_code == 200:
            return response.content if job_type == "tts" else response.text
        elif response.status_code != 202:
            raise RuntimeError(
                f"{job_type} job failed with HTTP {response.status_code}: {response.text}"
            )
        time.sleep(1)

    set_job(job_id, {"status": "running", f"{job_type}_status": "timeout"})
    raise TimeoutError(
        f"{job_type} Job {job_name} did not finish within {timeout_seconds} seconds."
    )

def list_available_voices() -> list[dict]:
    response = s3.list_objects_v2(
        Bucket=RUSTFS_BUCKET_IN,
        Prefix=PUBLIC_VOICE_PREFIX,
    )
    voices = {}
    for obj in response.get("Contents", []):
        key = obj["Key"]
        path = PurePosixPath(key)
        if path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        # famous_people/seth_rogan/clip1.wav
        _, voice_id, filename = path.parts # this will fail if the path is not exactly 3 parts...
        # Create the voice entry if it does not exist, and append the clip to the list of clips for that voice.
        voices.setdefault(voice_id,
            {
                "id": voice_id,
                "name": voice_id.replace("_", " ").title(),
                "clips": [],
            },
        )
        voices[voice_id]["clips"].append({
            "id": filename,
            "name": path.stem,
        })
    return sorted(
        voices.values(),
        key=lambda voice: voice["name"].lower(),
    )



def get_reference_audio_stream(object_key: str):
    """
    Open reference audio from RustFS for streaming to the browser.
    """
    response = s3.get_object(
        Bucket=RUSTFS_BUCKET_IN,
        Key=object_key,
    )
    return response["Body"]


# ---------------------------------------------------------------------------
# Full creation pipeline
# ---------------------------------------------------------------------------
def generate_script(receiver: str, caller: str, job_id: str)-> str:
    """
    Generate a short ringtone script.
    """
    prompt = (
        "You are a ringtone script writer. Generate a short, cute phone call script.\n\n"
        "CONTEXT:\n"
        f"- Caller: {caller}\n"
        f"- Receiver: {receiver}\n"
        f"- Narrator/Voice: {caller}\n\n"
        "INSTRUCTIONS:\n"
        f"- Output ONLY the script text (nothing else)\n"
        f"- The script is meta - it discusses the call itself and the fact that someone is calling\n"
        f"- Include the caller's name ({caller}) and receiver's name ({receiver}) naturally in the dialogue\n"
        f"- Keep it around 100 words\n"
        f"- Write it to be heard by the receiver ({receiver})\n"
        f"NARRATOR:\n"
        f"The script is narrated by {caller} (the caller) in 1st person.\n"
        f"{caller} describes their situation calling {receiver}."
    )
    job_name = submit_job("llama", prompt)
    set_job(job_id, {
        "status": "running",
        "llm_job_id": job_name,
        "llm_status": "submitted",
    })
    script = wait_for_result(
        job_id,
        "llama",
        job_name
    )
    return script

def create_ringtone(job_id: str, receiver: str, caller: str, voice_clip_path: str):
    set_job(job_id, {"status": "running"})
    try:
        # 1. Generate script using LLM
        script = generate_script(receiver=receiver, caller=caller, job_id=job_id)

        # 2. Generate signed URL for reference audio
        reference_audio_url = create_read_signed_url(voice_clip_path)

        # 3. Submit TTS Job
        tts_job = submit_job(job_type="tts", prompt=script, reference_audio_url=reference_audio_url)
        set_job(job_id, {
            "status": "running",
            "tts_job_id": tts_job,
            "tts_status": "submitted",
        })

        # 4. Wait for TTS result
        wav_bytes = wait_for_result(job_id, "tts", tts_job)
        set_job(job_id, {
            "status": "running",
            "tts_status": "completed",
        })

        # 5. Store the ringtone
        output_key = save_ringtone(wav_bytes=wav_bytes, caller=caller)
        set_job(job_id, {
            "status": "done",
            "output_key": output_key,
            "script": script,
        })

    except Exception as exc:
        set_job(job_id, {
            "status": "failed",
            "error": str(exc),
        })


if __name__ == "__main__":
    print(create_ringtone(
        receiver="Viktor",
        caller="Mille",
        voice_clip_path="uploads/reference.wav"
    ))
