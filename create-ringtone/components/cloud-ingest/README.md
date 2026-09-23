# Ingestion Pipeline

The homelab in this project is behind CGNAT, so the Kubernetes cluster is not exposed directly to the internet. Audio files are therefore uploaded to Google Cloud Storage (GCS) first. When a file is successfully created in the bucket, GCS publishes a notification to Pub/Sub. A worker running in Kubernetes keeps an outbound Pub/Sub connection open. When a notification arrives, the worker downloads the corresponding file from GCS and stores it in the local object storage.

```text
Edge device
    |
    | 
    v
GCS bucket
    |
    | 
    v
Pub/Sub topic
    |
    v
Pull subscription
    ^
    | outbound StreamingPull connection
    v
Kubernetes ingest worker
    |
    | 
    v
RustFS
```


##  GCP setup
Create a GCP project before running these commands. The commands below assume that the Google Cloud CLI is installed and authenticated.

### Variables
Replace `XXXX` with the GCP project ID.
```bash
PROJECT_ID=XXXX
BUCKET=voice-upload-$PROJECT_ID
PUBSUB=voice-upload
K8SSA=voice-upload-ingest
```
The bucket name includes the project ID because GCS bucket names must be globally unique.


### Select the project and enable APIs
```bash
gcloud config set project $PROJECT_ID
gcloud services enable \
  storage.googleapis.com \
  pubsub.googleapis.com \
  iam.googleapis.com
```

### Create the upload bucket
```bash
gcloud storage buckets create gs://$BUCKET \
  --location=EU \
  --uniform-bucket-level-access
```

### Create the Pub/Sub topic
```bash
gcloud pubsub topics create $PUBSUB
```

### Create the pull subscription
```bash
gcloud pubsub subscriptions create $PUBSUB-ingest \
  --topic=$PUBSUB \
  --message-retention-duration=31d
```

### Notify Pub/Sub when an upload finishes
```bash
gcloud storage buckets notifications create gs://$BUCKET \
  --topic=$PUBSUB \
  --event-types=OBJECT_FINALIZE 
```


### Create the homelab service account
```bash
gcloud iam service-accounts create $K8SSA
```

### Allow it to consume the subscription
```bash
gcloud pubsub subscriptions add-iam-policy-binding $PUBSUB-ingest \
  --member="serviceAccount:$K8SSA@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/pubsub.subscriber"
```


### Allow it to download uploaded objects
```bash
gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member="serviceAccount:$K8SSA@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"
```


## Kubernetes credentials

The worker runs outside GCP, so this simple setup uses a GCP service-account JSON key. From the repository root, create the key.
```bash
gcloud iam service-accounts keys create \
  create-ringtone/components/cloud-ingest/resources/gcp-ingest-secret.json \
  --iam-account="$K8SSA@$PROJECT_ID.iam.gserviceaccount.com"
```
DO NOT COMMMIT THIS FILE! Now the kustomize commands should be reproducible.
