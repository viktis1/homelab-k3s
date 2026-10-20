variable "project_id" {
  description = "GCP project to manage (the project itself already exists)."
  type        = string
  default     = "ringtone-k8s"
}

variable "k3s_issuer_uri" {
  description = "OIDC issuer advertised by the k3s cluster."
  type        = string
  default     = "https://kubernetes.default.svc.viktor.cluster"
}


