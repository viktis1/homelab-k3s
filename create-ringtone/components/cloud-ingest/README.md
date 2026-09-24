# Ingestion Pipeline

The homelab in this project is behind CGNAT, so the Kubernetes cluster is not exposed directly to the internet. Audio files are therefore uploaded to Google Cloud Storage (GCS) first. When a file is successfully created in the bucket, GCS publishes a notification to Pub/Sub. A worker running in Kubernetes keeps an outbound Pub/Sub connection open. When a notification arrives, the worker downloads the corresponding file from GCS and stores it in the local object storage. 

```text
Edge device
    | 
    v
GCS bucket
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
    v
RustFS
```


##  GCP setup
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


### Create the Google Service Account (GSA)
```bash
gcloud iam service-accounts create $GSA
```

### Give the GSA access to Pub/Sub and GCS
```bash
gcloud pubsub subscriptions add-iam-policy-binding $PUBSUB-ingest \
  --member="serviceAccount:$K8SSA@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/pubsub.subscriber"

gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member="serviceAccount:$K8SSA@$PROJECT_ID.iam.gserviceaccount.com" \
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
