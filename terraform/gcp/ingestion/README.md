# Manage GCP ingestion with Terraform

This Terraform configuration manages the GCP resources used by the `cloud-ingest` pipeline: the GCS bucket, Pub/Sub topic, subscription and bucket notification, IAM permissions, and Kubernetes Workload Identity Federation (WIF).

It can either create these resources in a new GCP project or adopt the resources previously created manually using [`create-ringtone/components/cloud-ingest/README.md`](../../../create-ringtone/components/cloud-ingest/README.md).

## Configuration

Set the project and other inputs in `variables.tf`. Authenticate Terraform with Google Cloud Application Default Credentials, for example:

```bash
gcloud auth application-default login
```

## Deploy

From the repository root:

```bash
terraform -chdir=terraform/gcp/ingestion init
terraform -chdir=terraform/gcp/ingestion plan
terraform -chdir=terraform/gcp/ingestion apply
```

Review the plan before approving the apply.

## Adopt existing resources

If the resources already exist because they were created by following [`create-ringtone/components/cloud-ingest/README.md`](../../../create-ringtone/components/cloud-ingest/README.md), rename [`terraform/gcp/ingestion/imports.tf.applied`](terraform/gcp/ingestion/imports.tf.applied) to [`terraform/gcp/ingestion/iimports.tf`](`terraform/gcp/ingestion/iimports.tf`) **before** running the commands above. Terraform loads `.tf` files automatically, and the import blocks tell it to adopt those existing resources instead of trying to create them.

After the first successful apply, rename `imports.tf` back to `imports.tf.applied`. The imported resources remain in Terraform state and continue to be managed by `main.tf`; the import blocks are no longer required. Leave the import file inactive when provisioning a new project.