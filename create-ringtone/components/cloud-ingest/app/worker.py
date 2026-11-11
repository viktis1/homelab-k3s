import os
import uuid
from pathlib import PurePosixPath

import boto3
from botocore.config import Config
from google.cloud import pubsub_v1, storage

import time
import requests

from database import init_db, register_voice, update_voice_language

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
SUBSCRIPTION = os.environ["PUBSUB_SUBSCRIPTION"]
RUSTFS_BUCKET = os.environ["RUSTFS_BUCKET"]


GPU_ORCHESTRATOR_URL = "http://gpu-orchestrator.gpu-orchestrator.svc.viktor.cluster:8000" # is this correct? 
RUSTFS_INTERNAL_URL = "http://rustfs.create-ringtone.svc.viktor.cluster:9000"

class InvalidUploadError(Exception):
    """An upload that cannot be processed."""
    pass

gcs = storage.Client()

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["RUSTFS_ENDPOINT"],
    aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],
    aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],
    region_name="us-east-1", # Region is required for S3 SigV4 signing
    config=Config(s3={"addressing_style": "path"}),
)

def classify_language(object_key: str) -> str:
    # Signed URL for the GPU pod to download the recording
    signed_s3 = boto3.client(
        "s3",
        endpoint_url=RUSTFS_INTERNAL_URL,
        aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],
        aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

    audio_url = signed_s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": RUSTFS_BUCKET, "Key": object_key},
        ExpiresIn=1800,
    )
    print(f"Generated signed URL for LID: {audio_url}")

    # Submit GPU job
    response = requests.post(
        f"{GPU_ORCHESTRATOR_URL}/jobs/lid",
        json={"audio_url": audio_url},
        timeout=30,
    )
    response.raise_for_status()
    job_name = response.json()["job"]

    # Wait for classification
    deadline = time.monotonic() + 300 # 5 minutes

    while time.monotonic() < deadline:
        response = requests.get(
            f"{GPU_ORCHESTRATOR_URL}/jobs/lid/{job_name}",
            timeout=30,
        )

        if response.status_code == 200:
            return response.json()["lang"]

        if response.status_code != 202:
            response.raise_for_status()

        time.sleep(12)

    raise TimeoutError(f"LID job {job_name} timed out")

def ensure_bucket():
    buckets = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    if RUSTFS_BUCKET not in buckets:
        print(f"\nBUCKET WAS NOT FOUND IN RUSTFS, CREATING IT: {RUSTFS_BUCKET}\n")
        s3.create_bucket(Bucket=RUSTFS_BUCKET)


def copy_object(bucket, name, generation):
    blob = gcs.bucket(bucket).blob(
        name,
        generation=int(generation),
    )
    blob.reload()  # Metadata is not available until the blob is reloaded

    gcs_path = PurePosixPath(name)
    if name.startswith("famous_people/"):
        # Public recordings: deterministic UUID from original path
        voice_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ringtone:{name}"))
        user_id = None
        voice_name = gcs_path.parent.name
        rustfs_path = f"famous_people/{voice_name}/{voice_uuid}{gcs_path.suffix}"
        public = True
    else:
        # Personal recordings: UUID supplied by Android client
        parts = name.split("/")
        if len(parts) != 3 or parts[0] != "users":
            raise InvalidUploadError(f"Invalid upload path: {name}")
        user_id = parts[1]
        voice_name = gcs_path.stem
        try:
            voice_uuid = str(uuid.UUID(blob.metadata["uuid"]))
        except (KeyError, ValueError, TypeError):
            raise InvalidUploadError(
                f"Missing or invalid UUID metadata: gs://{bucket}/{name}"
            )
        rustfs_path = f"users/{user_id}/{voice_uuid}{gcs_path.suffix}"
        public = False

    # Copy recording from GCS to RustFS
    data = blob.download_as_bytes()
    s3.put_object(
        Bucket=RUSTFS_BUCKET,
        Key=rustfs_path,
        Body=data,
    )
    print(f"Copied gs://{bucket}/{name} -> {RUSTFS_BUCKET}/{name}")

    # Register recording
    register_voice(
        voice_uuid=voice_uuid,
        user_id=user_id,
        contact=voice_name,
        file_path=rustfs_path,
        public=public,
    )
    print(f"Registered voice-upload {voice_uuid}({voice_name}, user={user_id})")

    # Classify language
    language = classify_language(rustfs_path)

    update_voice_language(voice_uuid, language)# Register recording
    print("language was detected and updated in the database: \n", language)


def callback(message):
    try:
        attrs = message.attributes
        copy_object(
            attrs["bucketId"], #The bucket ID comes in the message
            attrs["objectId"], # The object ID comes in the message
            attrs["objectGeneration"], # The object generation comes in the message
        )
        message.ack()
    except InvalidUploadError as e:
        print(f"Rejected upload: {e}")
        message.ack()
    except Exception as e:
        print(f"Transfer failed: {e}")
        message.nack()


if __name__ == "__main__":
    init_db()
    ensure_bucket()
    with pubsub_v1.SubscriberClient() as subscriber:
        subscription = subscriber.subscription_path(PROJECT, SUBSCRIPTION)
        future = subscriber.subscribe(subscription, callback=callback) # This will extend the acknowledge deadline during callback (up to 1 hour): https://docs.cloud.google.com/pubsub/docs/lease-management
        print(f"Listening on {subscription}")
        try:
            future.result()
        except KeyboardInterrupt:
            future.cancel()