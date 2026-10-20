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

  # Don't expire the subscription if the homelab is offline.
  expiration_policy {
    ttl = ""
  }
}

resource "google_pubsub_topic_iam_member" "ringtone_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.ringtone_generate.name

  role   = "roles/pubsub.publisher"
  member = "user:isaksenviktor@gmail.com"
}