# Create a Pub/Sub topic and subscription for the ringtone generation queue.
resource "google_pubsub_topic" "ringtone_generate" {
  name    = "ringtone-generate"
  project = var.project_id
}
resource "google_pubsub_subscription" "ringtone_generate_worker" {
  name    = "ringtone-generate-worker"
  project = var.project_id
  topic = google_pubsub_topic.ringtone_generate.id
  # Keep jobs while the homelab is offline.
  message_retention_duration = "2678400s" # 31 days
  # Don't expire the subscription if the homelab doesn't pull from it for long time.
  expiration_policy {
    ttl = ""
  }
}

# Grant the user that will be running the homelab the ability to publish messages to the queue.
resource "google_pubsub_topic_iam_member" "ringtone_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.ringtone_generate.name
  role   = "roles/pubsub.publisher"
  member = "user:isaksenviktor@gmail.com"
}

# Create SA
resource "google_service_account" "ringtone_worker" {
  project      = var.project_id
  account_id   = "create-ringtone-pubsub-watcher"
  display_name = "Ringtone generation Pub/Sub worker"
}
# Bind it to the workload identity pool so that the homelab can use the SA.
resource "google_service_account_iam_member" "ringtone_worker_wif" {
  service_account_id = google_service_account.ringtone_worker.name
  role = "roles/iam.workloadIdentityUser"
  member = "principal://iam.googleapis.com/projects/${data.google_project.current.number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.homelab.workload_identity_pool_id}/subject/system:serviceaccount:create-ringtone:create-ringtone-pubsub-watcher"
}
# Give the SA IAM permissions
resource "google_pubsub_subscription_iam_member" "ringtone_worker_subscriber" {
  project      = var.project_id
  subscription = google_pubsub_subscription.ringtone_generate_worker.name
  role = "roles/pubsub.subscriber"
  member = "serviceAccount:${google_service_account.ringtone_worker.email}"
}

