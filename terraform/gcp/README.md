# Google Cloud Infrastructure

This directory contains the Terraform configuration for the Google Cloud resources used by the create-ringtone application.

Terraform manages the cloud infrastructure required for audio ingestion and asynchronous ringtone generation.

## Managed Infrastructure

**Audio ingestion**
- Google Cloud Storage bucket for uploaded audio.
- Pub/Sub notifications for completed uploads.
- Subscription for the Kubernetes ingestion worker.

**Ringtone generation**
- Pub/Sub topic for generation requests.
- Subscription for the ringtone generation worker.
- IAM permissions for publishing and consuming messages.

**Authentication**
- Google service accounts and IAM permissions.
- Workload Identity Federation between Kubernetes and Google Cloud.

## Configuration

Configuration variables are defined in `variables.tf`.

Terraform uses Google Cloud Application Default Credentials for authentication.

```bash
gcloud auth application-default login
```

## Deployment

Run from the repository root:

```bash
terraform -chdir=terraform/gcp init
terraform -chdir=terraform/gcp plan
terraform -chdir=terraform/gcp apply
```

Review the Terraform plan before applying changes.

## Existing Resources

Some resources were originally created manually and later migrated to Terraform.

The `imports.tf.applied` file documents the Terraform imports used during this migration. These resources are now managed through the Terraform state.
