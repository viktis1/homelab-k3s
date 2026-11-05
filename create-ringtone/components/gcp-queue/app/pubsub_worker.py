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
    name = message.attributes["objectId"]
    # find uuid and job_id from filepath: users/<firebase_uid>/<job_id>.json
    _, uid, filename = name.split("/")
    job_id = uuid.UUID(filename.removesuffix(".json"))
    # Create the payload format. The keys are ["receiver", "caller", "voice_id", "clip_id"] + ["job_id"]
    blob = gcs.bucket(REQUEST_BUCKET).blob(name)
    payload = json.loads(blob.download_as_bytes())
    payload["job_id"] = str(job_id)
    return uid, payload

def callback(message):
    try:
        uid, payload = get_request(message)
        response = requests.post(
            f"{ORCHESTRATOR_URL}/generate",
            json=payload,
            headers={
                "X-Worker-Token": os.environ["INTERNAL_WORKER_TOKEN"],
                "X-User-ID": uid,
            },
            timeout=30,
        )
        if response.status_code in (400, 403, 422):
            print(f"Rejected request: {response.text}")
            message.ack()
            return

        response.raise_for_status()
        print(f"Submitted ringtone job: {response.json()['job_id']}")
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
            flow_control=pubsub_v1.types.FlowControl(max_messages=1),
        )
        print(f"Listening on {subscription}")
        try:
            future.result()
        except KeyboardInterrupt:
            future.cancel()