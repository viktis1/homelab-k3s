variable "project_id" {
  description = "Existing GCP project."
  type        = string
  default     = "ringtone-k8s"
}

variable "region" {
  description = "GCP region for Cloud Run and Artifact Registry."
  type        = string
  default     = "europe-west1"
}

variable "image_uri" {
  description = "Docker image for the enqueue API. Leave empty on the first apply to create Artifact Registry."
  type        = string
  default     = ""
}

variable "api_key" {
  description = "Shared X-API-Key header used by the phone shortcut."
  type        = string
  sensitive   = true
}
