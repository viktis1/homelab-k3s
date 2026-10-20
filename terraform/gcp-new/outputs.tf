output "topic" {
  value = google_pubsub_topic.ringtone_requests.id
}

output "subscription" {
  value = google_pubsub_subscription.ringtone_requests.id
}

output "image_prefix" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.enqueue.repository_id}/enqueue"
}

output "enqueue_url" {
  value = try(google_cloud_run_v2_service.enqueue[0].uri, null)
}
