import json
import os
from google.cloud import pubsub_v1
from app import CreateRingtoneRequest
from main import create_ringtone, PUBLIC_VOICE_PREFIX


PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
SUBSCRIPTION = os.environ["PUBSUB_SUBSCRIPTION"]


def callback(message):
    try:
        # Decode the Pub/Sub message
        payload = json.loads(message.data.decode("utf-8"))
        # Validate the message
        request = CreateRingtoneRequest(**payload)
        voice_clip_path = (
            f"{PUBLIC_VOICE_PREFIX}"
            f"{request.voice_id}/{request.clip_id}"
        )
        # Execute the existing ringtone pipeline
        tts_job, output_key, script = create_ringtone(
            receiver=request.receiver,
            caller=request.caller,
            voice_clip_path=voice_clip_path,
        )
        print(f"Ringtone created: {output_key}")
        # Acknowledge successful processing
        message.ack()
    except Exception as exc:
        print(f"Ringtone generation failed: {exc}")
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
            ),
        )
        print(f"Listening on {subscription}")
        try:
            future.result()
        except KeyboardInterrupt:
            future.cancel()