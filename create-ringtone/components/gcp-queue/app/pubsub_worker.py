import json
import os
import uuid

import requests
from google.cloud import pubsub_v1, storage


PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
SUBSCRIPTION = os.environ["PUBSUB_SUBSCRIPTION"]
ORCHESTRATOR_URL = os.environ["ORCHESTRATOR_URL"]
REQUEST_BUCKET = os.environ["RINGTONE_REQUEST_BUCKET"]

gcs = storage.Client()




def get_request(message):
    attrs = message.attributes

    name = attrs["objectId"]
    generation = int(attrs["objectGeneration"])

    # Expected: users/<firebase_uid>/<job_id>.json
    parts = name.split("/")
    uid = parts[1]
    filename = parts[2]

    # Validate the UUID4 job ID from the filename.
    job_uuid = uuid.UUID(filename[:-5])

    # Download the request from GCS.
    blob = gcs.bucket(REQUEST_BUCKET).blob(
        name,
        generation=generation,
    )

    # fields = ("receiver", "caller", "voice_id", "clip_id")
    payload = json.loads(blob.download_as_bytes())

    return uid, payload


def callback(message):
    try:
        uid, payload = get_request(message)

        # Existing orchestrator submission logic.
        response = requests.post(
            f"{ORCHESTRATOR_URL}/generate",
            json=payload,
            headers={
                "X-Worker-Token": os.environ["INTERNAL_WORKER_TOKEN"],
                "X-User-ID": uid,
            },
            timeout=30,
        )

        # Reject permanently invalid requests.
        if response.status_code in (400, 403, 422):
            print(f"Rejected request: {response.status_code} {response.text}")
            message.ack()
            return

        response.raise_for_status()

        job_id = response.json()["job_id"]
        print(f"Submitted ringtone job: {job_id}")

        message.ack()

    except Exception as exc:
        print(f"Ringtone submission failed: {exc}")
        message.nack()


if __name__ == "__main__":
    with pubsub_v1.SubscriberClient() as subscriber:
        subscription = subscriber.subscription_path(
            PROJECT,
            SUBSCRIPTION,
        )

        future = subscriber.subscribe(
            subscription,
            callback=callback,
            flow_control=pubsub_v1.types.FlowControl(
                max_messages=1,
                max_lease_duration=3600,
            ),
        )

        print(f"Listening on {subscription}")

        try:
            future.result()
        except KeyboardInterrupt:
            future.cancel()