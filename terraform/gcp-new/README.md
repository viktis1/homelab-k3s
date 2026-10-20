# Offline ringtone submissions — GCP side only

This adds one Cloud Run endpoint (`POST /enqueue`) to accept submissions while the K3s cluster is off. It publishes JSON into GCP Pub/Sub. A future K3s subscriber will pull the backlog and use the existing ringtone generation pipeline.

No Firestore, no extra database, no cloud-side status endpoint, and **no changes to the current K3s endpoints**.

## File locations

- `terraform/gcp/`: GCP resources managed by Terraform.
- `create-ringtone/components/queue-api/`: FastAPI app + Dockerfile deployed to Cloud Run.

These paths are relative to the `homelab-k3s` repository root.

## 1. GCP prerequisites

Use your existing GCP project, `ringtone-k8s`, where the current cloud-ingest Workload Identity Federation setup already exists.

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project ringtone-k8s
```

Terraform enables Pub/Sub, Artifact Registry, Cloud Run and IAM APIs. You need permission to configure those resources.

## 2. First Terraform apply: create Pub/Sub and Artifact Registry

From your repository root:

```bash
cp terraform/gcp/terraform.tfvars.example terraform/gcp/terraform.tfvars
openssl rand -hex 32
# Copy the generated key into `api_key` in terraform/gcp/terraform.tfvars.
# Keep the key for the iPhone Shortcut as well.

terraform -chdir=terraform/gcp init
terraform -chdir=terraform/gcp plan
terraform -chdir=terraform/gcp apply
```

Because `image_uri` is initially empty, this first apply creates the Pub/Sub topic, subscription, IAM and Artifact Registry repository, **but not Cloud Run**.

The key is a normal Cloud Run environment variable: Terraform state and Cloud Run configuration contain its value. This is a simple homelab tradeoff; don't commit `terraform.tfvars` or Terraform state. Your current root `.gitignore` already ignores both.

## 3. Build and push the Docker image

You need Docker installed and permission to push images to Artifact Registry.

```bash
gcloud auth configure-docker europe-west1-docker.pkg.dev

IMAGE=europe-west1-docker.pkg.dev/ringtone-k8s/ringtone-queue/enqueue:v1

docker build --platform linux/amd64 \
  -t "$IMAGE" create-ringtone/components/queue-api

docker push "$IMAGE"
```

This is a normal Docker image, stored in **GCP Artifact Registry**. The container itself has no GCP keys: Cloud Run automatically supplies credentials for its assigned service account.

## 4. Second Terraform apply: create Cloud Run

Edit `terraform/gcp/terraform.tfvars`:

```hcl
image_uri = "europe-west1-docker.pkg.dev/ringtone-k8s/ringtone-queue/enqueue:v1"
```

Then run:

```bash
terraform -chdir=terraform/gcp apply
terraform -chdir=terraform/gcp output enqueue_url
```

Cloud Run uses min instances 0 by default. There is no running VM and you pay according to Cloud Run's billing model when requests are served.

## 5. Test publishing a request

The endpoint accepts the same fields as your current `POST /generate` handler.

```bash
QUEUE_URL=$(terraform -chdir=terraform/gcp output -raw enqueue_url)
# Load your private key into QUEUE_KEY, for example from your password manager.
read -rsp "Queue API key: " QUEUE_KEY; echo

curl -i -X POST "$QUEUE_URL/enqueue" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $QUEUE_KEY" \
  -d '{"receiver":"Bob","caller":"Alice","voice_id":"seth_rogan","clip_id":"clip1.wav"}'
unset QUEUE_KEY
```

Expected response (HTTP 202):

```json
{
  "job_id": "4b5c1c27be77434fb74f3b5174a2d2e1",
  "status": "queued",
  "submitted_at": "2026-10-20T12:00:00+00:00"
}
```

For a smoke test before the K3s consumer exists, pull a message *manually* (this consumes one message if auto-acknowledged):

```bash
gcloud pubsub subscriptions pull ringtone-generate-worker \
  --project=ringtone-k8s \
  --limit=1 \
  --auto-ack
```

Don't use `--auto-ack` on requests you expect the future K3s worker to process.

For an **iPhone Shortcut**, use the "Get Contents of URL" action with POST, JSON body, and headers `Content-Type: application/json` and `X-API-Key: <your key>`. The returned `job_id` can be saved by the Shortcut.

## Later: K3s consumer

The `ringtone-generate-worker` subscription is ready, and the current GCP identity `voice-upload-ingest@ringtone-k8s.iam.gserviceaccount.com` is granted subscriber access. A later change can add a Pub/Sub StreamingPull consumer to your existing orchestrator, using your existing Workload Identity Federation setup. It should use the `job_id` supplied in each message.

Until that consumer exists, this implementation **only queues jobs**. It will not generate ringtones.

Pub/Sub can redeliver unacknowledged messages, and a subscription retains them for up to 31 days. Retaining unacknowledged messages for over 24 hours can incur storage charges. Without a consumer, the backlog will eventually expire; the queue is not permanent storage.
