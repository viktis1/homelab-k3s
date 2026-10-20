# Enable the services this small deployment needs.
resource "google_project_service" "apis" {
  for_each = toset([
    "pubsub.googleapis.com",
    "artifactregistry.googleapis.com",
    "run.googleapis.com",
    "iam.googleapis.com",
  ])

  service            = each.key
  disable_on_destroy = false
}

# Pub/Sub stores submissions while K3s is powered off.
resource "google_pubsub_topic" "ringtone_requests" {
  name       = "ringtone-generate"
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_subscription" "ringtone_requests" {
  name                       = "ringtone-generate-worker"
  topic                      = google_pubsub_topic.ringtone_requests.id
  message_retention_duration = "2678400s" # 31 days

  expiration_policy {
    ttl = "" # Do not expire if K3s is offline for 31+ days
  }
}

# Allow the existing Kubernetes WIF identity to consume queued requests later.
# This is the same Google service account used by the current cloud-ingest worker.
resource "google_pubsub_subscription_iam_member" "k3s_subscriber" {
  subscription = google_pubsub_subscription.ringtone_requests.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:voice-upload-ingest@${var.project_id}.iam.gserviceaccount.com"
}

# Cloud Run gets its own identity with only permission to publish to this topic.
resource "google_service_account" "enqueue" {
  account_id   = "ringtone-enqueue"
  display_name = "Ringtone Pub/Sub enqueue API"
  depends_on   = [google_project_service.apis]
}

resource "google_pubsub_topic_iam_member" "enqueue_publisher" {
  topic  = google_pubsub_topic.ringtone_requests.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.enqueue.email}"
}

# Where you push the Docker image before deploying Cloud Run.
resource "google_artifact_registry_repository" "enqueue" {
  location      = var.region
  repository_id = "ringtone-queue"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

# Image is optional on the first apply because the registry must exist first.
resource "google_cloud_run_v2_service" "enqueue" {
  count               = var.image_uri == "" ? 0 : 1
  name                = "ringtone-enqueue"
  location            = var.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.enqueue.email

    scaling {
      max_instance_count = 1
    }

    containers {
      image = var.image_uri

      ports {
        container_port = 8080
      }

      env {
        name  = "PUBSUB_TOPIC"
        value = google_pubsub_topic.ringtone_requests.id
      }

      env {
        name  = "ENQUEUE_API_KEY"
        value = var.api_key
      }
    }
  }

  depends_on = [google_pubsub_topic_iam_member.enqueue_publisher]
}

# Cloud Run is publicly reachable, while the Python API checks X-API-Key.
resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.image_uri == "" ? 0 : 1
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.enqueue[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
