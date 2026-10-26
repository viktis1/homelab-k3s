# Intention

This code, together with the infrastructure defined in `terraform/gcp/pubsub-queue.tf`, provides an additional way to request ringtone generation through Google Cloud Pub/Sub.

The main advantage is that users can submit ringtone generation requests even when the homelab is offline. Pub/Sub stores the messages until the Kubernetes worker is available to process them.

The worker forwards received requests to the existing ringtone orchestrator, monitors their progress, and acknowledges the Pub/Sub messages once generation has completed successfully.

# Missing functionality

This implementation is not quite finished.

Currently, the Pub/Sub worker can submit jobs and confirm that the resulting WAV files have been stored in RustFS. However, there is no mechanism for the original publisher to retrieve the completed ringtone. This is due to the create-ringtone-orchestrator currently storing job information (IDs, statuses, and output file locations) in an in-memory Python dictionary. 

## Planned improvements

I want to introduce a relational database, most likely PostgreSQL, to persist job metadata and eventually user information. The relevant part of the database for this project is to give users who uploaded pubsubs a way to access their generated ringtones.