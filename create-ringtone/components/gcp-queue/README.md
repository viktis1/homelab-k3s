# Pub/Sub Generation Queue

This component allows ringtone generation requests to be submitted through Google Cloud Pub/Sub, even when the homelab is offline.

Pub/Sub retains messages until the Kubernetes worker is available to process them.

Infrastructure is managed through `terraform/gcp/pubsub-queue.tf`.


## Architecture

### Uploading
```text
Client
   |
   v
Google Pub/Sub
   |
   v
Kubernetes Pub/Sub Worker
   |
   v
Ringtone Orchestrator
```
Each Pub/Sub message contains the information required to generate a ringtone, including a UUID4 job ID.

The worker forwards the request to the ringtone orchestrator and acknowledges the message once the orchestrator accepts it.

### Downloading 

The original publisher can retrieve the job status and download the completed ringtone using the job ID they created.

## Limitations

Pub/Sub guarantees delivery of generation requests, not successful ringtone generation.

Generation currently relies on FastAPI background tasks, which are not durable across orchestrator restarts.

Client can only download the ringtone when the server is up (which - admittedly - is rare)