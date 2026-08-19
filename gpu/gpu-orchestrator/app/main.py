from fastapi import FastAPI
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import PlainTextResponse

# Scripts to build the GPU-needing jobs.
from jobs.llamacpp import build_llama_job

# Static files for the web interface.
from pathlib import Path
from fastapi.responses import FileResponse

app = FastAPI()

# Create the static directory path for serving the index.html file.
STATIC_DIR = Path(__file__).parent / "static"
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")



config.load_incluster_config()
batch_api = client.BatchV1Api()
core_api = client.CoreV1Api()

# Health check endpoint
@app.get("/health")
def health():
    return {"status": "ok"}


# --------------------------------------------------------------------------------------------
# Define the different jobs that can be scheduled
JOB_TYPES = {
    "llama": {
        "namespace": "llm",
        "container": "llama",
    },
}
# Llama.cpp job request
class LlamaRequest(BaseModel):
    prompt: str = "Explain why the sky is blue in three sentences."
    hf_repo: str = "bartowski/Qwen3.8-27B-GGUF"
    hf_file: str = "Qwen3.8-27B-Q5_K_S.gguf"



@app.post("/jobs/llama")
def create_llama_job(request: LlamaRequest):
    job = build_llama_job(
        prompt=request.prompt,
        hf_repo=request.hf_repo,
        hf_file=request.hf_file
    )

    result = batch_api.create_namespaced_job(
        namespace="llm",
        body=job,
    )

    return {
        "job": result.metadata.name,
    }


@app.get("/jobs/{job_type}/{job_name}")
def get_job(job_type: str, job_name: str):

    job_config = JOB_TYPES.get(job_type)
    if job_config is None:
        raise HTTPException(
            status_code=404,
            detail="Unknown job type",
        )
    namespace = job_config["namespace"]

    try:
        job = batch_api.read_namespaced_job(
            name=job_name,
            namespace=namespace,
        )

    except ApiException as exc:
        if exc.status == 404:
            raise HTTPException(
                status_code=404,
                detail="Job not found",
            )

        raise HTTPException(
            status_code=500,
            detail=f"Failed to read Kubernetes Job: {exc.reason}",
        )

    # Get job status
    if job.status.succeeded:
        status = "completed"
    elif job.status.failed:
        status = "failed"
    elif job.status.active:
        status = "running"
    else:
        status = "pending"

    return {
        "job": job.metadata.name,
        "status": status,
    }


@app.get("/jobs/{job_type}/{job_name}/result", response_class=PlainTextResponse)
def get_job_result(job_type: str, job_name: str):

    job_config = JOB_TYPES.get(job_type)

    if job_config is None:
        raise HTTPException(
            status_code=404,
            detail="Unknown job type",
        )

    namespace = job_config["namespace"]
    container = job_config["container"]

    job = batch_api.read_namespaced_job(
        name=job_name,
        namespace=namespace,
    )

    if not job.status.succeeded:
        raise HTTPException(
            status_code=409,
            detail="Job has not completed successfully",
        )

    pods = core_api.list_namespaced_pod(
        namespace=namespace,
        label_selector=f"batch.kubernetes.io/job-name={job_name}",
    )

    if not pods.items:
        raise HTTPException(
            status_code=404,
            detail="Pod for Job not found",
        )

    pod = pods.items[0]

    result = core_api.read_namespaced_pod_log(
        name=pod.metadata.name,
        namespace=namespace,
        container=container,
    )

    return result