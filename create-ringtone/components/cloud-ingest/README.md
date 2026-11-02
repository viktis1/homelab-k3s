# Cloud Ingestion
This component transfers uploaded audio files from Google Cloud Storage into the homelab's local object storage.

Since the homelab operates behind CGNAT, incoming connections from the internet are not directly available. Google Cloud PubSub enables the Kubernetes worker to receive upload notifications through an outbound connection.

## Architecture

```text
Client
   |
   | Audio file + UUID metadata
   v
Google Cloud Storage
   |
   | Object finalized event
   v
Google PubSub
   |
   | outbound StreamingPull connection
   v
Kubernetes Ingest Worker
   |
   +-- RustFS (audio storage)
   |
   +-- PostgreSQL (UUID → file path)
```

## How it works



1. A client uploads an audio file to Google Cloud Storage, including a UUID in the object's custom metadata.
2. GCS publishes an upload notification to PubSub.
3. For all new notifications, the Kubernetes ingest worker retrieves the file and the accompanying metadata.
4. The worker stores the audio file in RustFS and registers {UUID, file path} in PostgreSQL.
5. The Pub/Sub message is acknowledged after successful processing.

The ingestion worker authenticates to Google Cloud using Workload Identity Federation (WIF), avoiding long-lived Google service account keys.

The required GCP infrastructure is managed through Terraform in `terraform/gcp/`.
