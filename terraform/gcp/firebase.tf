# Enable the Firebase API for the project. You have to accept terms of service via the Firebase console before terraform works... Firebase still in beta...
resource "google_firebase_project" "default" {
  provider = google-beta
  project  = var.project_id

  # depends_on = [google_project_service.enabled["firebase.googleapis.com"]]
}


resource "google_firebase_android_app" "ringtone" {
  provider = google-beta

  project      = google_firebase_project.default.project
  display_name = "Ringtone Goofer"
  package_name = "com.example.ringtone_goofer"

  sha1_hashes = [
    "F3AFB6479E9A8E1E41B8A4D5C1EEED06E8F6C706" # Expires in 2056
  ]
}

# Initialize Firebase Authentication
resource "google_identity_platform_config" "auth" {
  provider = google-beta
  project  = google_firebase_project.default.project

  # depends_on = [google_project_service.enabled["identitytoolkit.googleapis.com"]]
}

# Create OAuth webclient credentials manually... https://console.cloud.google.com/auth/clients
# | Setting                 | Value             |
# | App name                | Ringtone Goofer   |
# | User support email      | Your Google email |
# | Audience                | External          |
# | Developer contact email | Your Google email |
# 
# Then Google Auth Platform → Clients → Create client
# | Setting                       | Value                                                |
# | Application type              | Web application                                      |
# | Name                          | Ringtone Goofer Firebase Auth                        |
# | Authorized JavaScript origins | https://ringtone-k8s.firebaseapp.com                 |
# | Authorized redirect URIs      | https://ringtone-k8s.firebaseapp.com/__/auth/handler |
# 
# I have done this and copied the client id and secret into terraform/gcp/firebase-secret.auto.tfvars
# Decrypt with sops -d firebase-secret.auto.tfvars.sops > firebase-secret.auto.tfvars

variable "google_oauth_client_id" {
  type = string
}

variable "google_oauth_client_secret" {
  type      = string
  sensitive = true
}

resource "google_identity_platform_default_supported_idp_config" "google" {
  provider = google-beta
  project  = google_firebase_project.default.project

  enabled       = true
  idp_id        = "google.com"
  client_id     = var.google_oauth_client_id
  client_secret = var.google_oauth_client_secret

  # depends_on = [google_identity_platform_config.auth]
}