# Cloud Ingestion
This component transfers uploaded audio files from Google Cloud Storage into the homelab's local object storage.

Since the homelab operates behind CGNAT, incoming connections from the internet are not directly available. Google Cloud PubSub enables the Kubernetes worker to receive upload notifications through an outbound connection.

## Architecture

```text
Client
   |
   v
Google Cloud Storage
   |
   | Object finalized event
   v
Google PubSub
   | outbound StreamingPull connection
   v
Kubernetes Ingest Worker
   |
   v
RustFS
```

## How it works

1. A client uploads an audio file to Google Cloud Storage.
2. GCS publishes an upload notification to PubSub.
3. The Kubernetes ingest worker receives the notification.
4. The worker downloads the audio file and stores it in RustFS.

The ingestion worker authenticates to Google Cloud using Workload Identity Federation (WIF), avoiding long-lived Google service account keys.

The required GCP infrastructure is managed through Terraform in `terraform/gcp/`.


##  Manual GCP setup (DEPERECATED)

> **Note:** The manual setup instructions are preserved below for reference
> and for those who prefer configuring GCP resources directly.


Create a GCP project before running these commands. The commands below assume that the Google Cloud CLI is installed and authenticated.

SOME COMMANDS ASSUME YOU ARE RUNNING THEM FROM THE REPOSITORY ROOT.

### Variables
Replace `XXXX` with the GCP project ID.
```bash
# Google Cloud 
PROJECT_ID=XXXX
BUCKET=voice-upload-$PROJECT_ID
PUBSUB=voice-upload

GSA=voice-upload-ingest
KSA=cloud-ingest

WIF_POOL=homelab
PROVIDER_ID=k3s-homelab
```
The bucket name includes the project ID because GCS bucket names must be globally unique. All other variables can be picked freely.


### Select the project and enable APIs
```bash
gcloud config set project $PROJECT_ID
gcloud services enable \
  storage.googleapis.com \
  pubsub.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  cloudresourcemanager.googleapis.com
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


### Create the Google Service Account (GSA)
```bash
gcloud iam service-accounts create $GSA
```

### Give the GSA access to Pub/Sub and GCS
```bash
gcloud pubsub subscriptions add-iam-policy-binding $PUBSUB-ingest \
  --member="serviceAccount:$GSA@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/pubsub.subscriber"

gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member="serviceAccount:$GSA@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"
```

## Workload Identity Federation (WIF)
Since GCP supports WIF from external kubernetes cluster, we will use that, so that we don't have to store long-lived credentials to Google.  

```text
Kubernetes ServiceAccount (KSA)
        |
        | short-lived Kubernetes token
        v
Workload Identity Pool / Provider
        |
        | verifies token using K3s public keys
        v
Google Service Account (GSA)
        |
        +--> Pub/Sub
        +--> GCS
```


### Create the Workload Identity Pool
The pool identifies identities that don't originate in Google Cloud.
```bash
gcloud iam workload-identity-pools create $WIF_POOL \
  --location=global \
  --display-name="Homelab Kubernetes"
```



### Add K3s as an OIDC provider

To allow the server to reach GCP WIF, the server needs to be both authenticated (Who am I) and authorized (What can I do). To authenticate that a SA, it therefore needs to be able to confirm that the SA originates from the server.

```bash
ISSUER=$(kubectl get --raw /.well-known/openid-configuration | jq -r .issuer)
kubectl get --raw /openid/v1/jwks > create-ringtone/components/cloud-ingest/cluster-jwks.json

echo "$ISSUER"
```

```bash
gcloud iam workload-identity-pools providers create-oidc $PROVIDER_ID \
  --location=global \
  --workload-identity-pool=$WIF_POOL \
  --issuer-uri="$ISSUER" \
  --attribute-mapping="google.subject=assertion.sub" \
  --jwk-json-path=create-ringtone/components/cloud-ingest/cluster-jwks.json
```

For the ingest worker, the mapped Kubernetes identity is:

```bash
echo system:serviceaccount:create-ringtone:$KSA
```

Feel free to remove the public cluster keys after (it's not unsafe to keep, but prettier without).

### Allow the KSA to impersonate the GSA
This is where we define the authorization of the GSA (and therefore the KSA)
```bash
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
```
```bash
gcloud iam service-accounts add-iam-policy-binding $GSA@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member="principal://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$WIF_POOL/subject/system:serviceaccount:create-ringtone:$KSA"
```

### Generate the WIF credential configuration

```bash
gcloud iam workload-identity-pools create-cred-config \
  projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$WIF_POOL/providers/$PROVIDER_ID \
  --service-account=$GSA@$PROJECT_ID.iam.gserviceaccount.com \
  --credential-source-file=/var/run/service-account/token \
  --credential-source-type=text \
  --output-file=create-ringtone/components/cloud-ingest/resources/credential-configuration.json
```

`credential-configuration.json` contains no private key and does not need to be stored as a Secret. That is the advantage of WIF.

# Links
https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-kubernetes
https://medium.com/israeli-tech-radar/oauth-2-0-and-openid-connect-for-dummies-6fa6e995d6d5
https://www.jscape.com/glossary/outbound-connection
