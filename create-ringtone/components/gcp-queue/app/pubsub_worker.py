import json
import os
import time

import requests
from google.cloud import pubsub_v1


PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
SUBSCRIPTION = os.environ["PUBSUB_SUBSCRIPTION"]

ORCHESTRATOR_URL = os.environ["ORCHESTRATOR_URL"]


def callback(message):
    try:
        # Decode the message received from Pub/Sub.
        payload = json.loads(message.data.decode("utf-8"))
        # Submit the job to the create-ringtone orchestrator.
        response = requests.post(
            f"{ORCHESTRATOR_URL}/generate",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        job_id = response.json()["job_id"]
        print(f"Submitted ringtone job: {job_id}")
        # Monitor the job.
        deadline = time.monotonic() + 3000
        while time.monotonic() < deadline:
            response = requests.get(
                f"{ORCHESTRATOR_URL}/status/{job_id}",
                timeout=30,
            )
            response.raise_for_status()
            job = response.json()
            status = job["status"]
            if status == "done":
                print(f"Ringtone completed: {job['output_key']}")
                message.ack()
                return
            if status == "failed":
                raise RuntimeError(job.get("error", "Unknown error"))
            time.sleep(10)
        raise TimeoutError(f"Ringtone job {job_id} timed out")

    except Exception as exc:
        print(f"Ringtone processing failed: {exc}")
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