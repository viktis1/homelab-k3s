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