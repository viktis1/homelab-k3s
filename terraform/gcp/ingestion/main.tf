terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
}

locals {
  bucket_name = "voice-upload-${var.project_id}"
  ksa_subject = "system:serviceaccount:create-ringtone:cloud-ingest"
}

# Only the project itself needs to exist beforehand.
resource "google_project_service" "enabled" {
  for_each = toset([
    "storage.googleapis.com",
    "pubsub.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "voice_upload" {
  name                        = local.bucket_name
  project                     = var.project_id
  location                    = "EU"
  uniform_bucket_level_access = true
  force_destroy               = false

  depends_on = [google_project_service.enabled["storage.googleapis.com"]]
}

resource "google_pubsub_topic" "voice_upload" {
  name    = "voice-upload"
  project = var.project_id

  depends_on = [google_project_service.enabled["pubsub.googleapis.com"]]
}

resource "google_pubsub_subscription" "voice_upload_ingest" {
  name                       = "voice-upload-ingest"
  project                    = var.project_id
  topic                      = google_pubsub_topic.voice_upload.id
  message_retention_duration = "1209600s" # 14 days
}

resource "google_service_account" "voice_upload_ingest" {
  account_id = "voice-upload-ingest"
  project    = var.project_id

  depends_on = [google_project_service.enabled["iam.googleapis.com"]]
}

resource "google_pubsub_subscription_iam_member" "ingest_subscriber" {
  subscription = google_pubsub_subscription.voice_upload_ingest.id
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.voice_upload_ingest.email}"
}

resource "google_storage_bucket_iam_member" "ingest_object_viewer" {
  bucket = google_storage_bucket.voice_upload.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.voice_upload_ingest.email}"
}

# Cloud Storage publishes notifications under its Google-managed service agent.
# This permission is needed when reconstructing the pipeline in a fresh project.
data "google_storage_project_service_account" "gcs" {
  project = var.project_id

  depends_on = [google_project_service.enabled["storage.googleapis.com"]]
}

resource "google_pubsub_topic_iam_member" "gcs_publisher" {
  topic  = google_pubsub_topic.voice_upload.id
  role   = "roles/pubsub.publisher"
  member = data.google_storage_project_service_account.gcs.member
}

resource "google_storage_notification" "voice_upload_finalize" {
  bucket         = google_storage_bucket.voice_upload.name
  topic          = google_pubsub_topic.voice_upload.id
  event_types    = ["OBJECT_FINALIZE"]
  payload_format = "JSON_API_V1"

  depends_on = [google_pubsub_topic_iam_member.gcs_publisher]
}

# WIF for the external k3s cluster. The JWKS is the cluster's PUBLIC keys.
resource "google_iam_workload_identity_pool" "homelab" {
  workload_identity_pool_id = "homelab"
  display_name              = "Homelab Kubernetes"

  depends_on = [google_project_service.enabled["iam.googleapis.com"]]
}

resource "google_iam_workload_identity_pool_provider" "k3s" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.homelab.workload_identity_pool_id
  workload_identity_pool_provider_id = "k3s-homelab"
  attribute_mapping = {
    "google.subject" = "assertion.sub"
  }

  oidc {
    issuer_uri = var.k3s_issuer_uri
    jwks_json  = file("${path.module}/../../../create-ringtone/components/cloud-ingest/cluster-jwks.json")
  }
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_service_account_iam_member" "k3s_impersonation" {
  service_account_id = google_service_account.voice_upload_ingest.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principal://iam.googleapis.com/projects/${data.google_project.current.number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.homelab.workload_identity_pool_id}/subject/${local.ksa_subject}"
}