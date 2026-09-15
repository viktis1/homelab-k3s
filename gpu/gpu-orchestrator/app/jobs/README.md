# Template for creating job-files for gpu-orchestrator
This is a friendly reminder to myself for how to write the files under jobs/

- Define "NAMESPACE" and "JOB_TYPE" as string variables.
- Create a "Request" class for the payload of the html.
- Create a "build_job" function that creates a kubernetes manifest for building a job.
-  create a "read_results" function. The output of this function is returned directly to the user.