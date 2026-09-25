import os

import boto3
from botocore.config import Config
from google.cloud import pubsub_v1, storage

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
SUBSCRIPTION = os.environ["PUBSUB_SUBSCRIPTION"]
RUSTFS_BUCKET = os.environ["RUSTFS_BUCKET"]

gcs = storage.Client()

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["RUSTFS_ENDPOINT"],
    aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],
    aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],
    region_name="us-east-1", # Region is required for S3 SigV4 signing
    config=Config(s3={"addressing_style": "path"}),
)


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
    data = blob.download_as_bytes() # Download the object from GCS into RAM
    s3.put_object(
        Bucket=RUSTFS_BUCKET,
        Key=name,
        Body=data,
    )
    print(f"Copied gs://{bucket}/{name} -> {RUSTFS_BUCKET}/{name}")


def callback(message):
    try:
        attrs = message.attributes
        copy_object(
            attrs["bucketId"], #The bucket ID comes in the message
            attrs["objectId"], # The object ID comes in the message
            attrs["objectGeneration"], # The object generation comes in the message
        )
        message.ack()
    except Exception as e:
        print(f"Transfer failed: {e}")
        message.nack()


if __name__ == "__main__":
    ensure_bucket()
    with pubsub_v1.SubscriberClient() as subscriber:
        subscription = subscriber.subscription_path(PROJECT, SUBSCRIPTION)
        future = subscriber.subscribe(subscription, callback=callback) # This will extend the acknowledge deadline during callback (up to 1 hour): https://docs.cloud.google.com/pubsub/docs/lease-management
        print(f"Listening on {subscription}")
        try:
            future.result()
        except KeyboardInterrupt:
            future.cancel()