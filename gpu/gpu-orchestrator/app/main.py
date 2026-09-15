import time
import uuid

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from pydantic import ValidationError

from jobs import llamacpp, tts


app = FastAPI()


config.load_incluster_config()

batch_api = client.BatchV1Api()
core_api = client.CoreV1Api()


# ---------------------------------------------------------
# Job registry
# ---------------------------------------------------------

JOB_TYPES = {
    module.JOB_TYPE: module
    for module in (
        llamacpp, # dictionary for this becomes {"llama": llamacpp},
        tts, # dictionary for this becomes {"tts": tts},
    )
}

# Register handler-specific FastAPI endpoints
for handler in JOB_TYPES.values():
    if hasattr(handler, "router"):
        app.include_router(handler.router)

def get_job_handler(job_type: str):
    handler = JOB_TYPES.get(job_type)
    return handler


def get_job_status(job):
    if job.status.succeeded:
        return "completed"
    if job.status.failed:
        return "failed"
    if job.status.active:
        return "running"
    return "pending"


def get_job(job_name: str, namespace: str):
    try:
        return batch_api.read_namespaced_job(
            name=job_name,
            namespace=namespace,
        )
    except ApiException as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read Kubernetes Job: {exc.reason}",
        )


def get_job_pod(job_name: str, namespace: str):
    pods = core_api.list_namespaced_pod(
        namespace=namespace,
        label_selector=f"batch.kubernetes.io/job-name={job_name}",
    )
    if not pods.items:
        raise HTTPException(
            status_code=404,
            detail="Pod for Job not found",
        )
    return pods.items[0]


# ---------------------------------------------------------
# Endpoint 1: Start any GPU job
# ---------------------------------------------------------

@app.post("/jobs/{job_type}", status_code=202)
def start_job(
    job_type: str,
    payload: dict = Body(...),
):
    handler = get_job_handler(job_type)

    try:
        request = handler.Request.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(),
        )

    job_name = f"{job_type}-{uuid.uuid4().hex[:12]}"

    job = handler.build_job(
        core_api=core_api,
        request=request,
        job_name=job_name,
    )

    # main.py owns the Kubernetes Job identity.
    job.setdefault("metadata", {})
    job["metadata"]["name"] = job_name
    job["metadata"].pop("generateName", None)

    try:
        batch_api.create_namespaced_job(
            namespace=handler.NAMESPACE,
            body=job,
        )
    except ApiException as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create Kubernetes Job: {exc.reason}",
        )

    return {
        "job_type": job_type,
        "job": job_name,
        "status": "submitted",
        "result_url": f"/jobs/{job_type}/{job_name}",
    }


# ---------------------------------------------------------
# Endpoint 2: Get status or result
# ---------------------------------------------------------

@app.get("/jobs/{job_type}/{job_name}")
def get_result(
    job_type: str,
    job_name: str,
):
    handler = get_job_handler(job_type)

    job = get_job(
        job_name=job_name,
        namespace=handler.NAMESPACE,
    )

    status = get_job_status(job)

    if status == "completed":
        pod = get_job_pod(
            job_name=job_name,
            namespace=handler.NAMESPACE,
        )

        return handler.read_result(
            core_api=core_api,
            pod=pod,
            job_name=job_name,
        )

    if status == "failed":
        status_code = 500
    else:
        status_code = 202

    return JSONResponse(
        status_code=status_code,
        content={
            "job_type": job_type,
            "job": job_name,
            "status": status,
        },
    )