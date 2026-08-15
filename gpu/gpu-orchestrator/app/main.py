from fastapi import FastAPI
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Scripts to build the GPU-needing jobs.
from jobs.llamacpp import build_llama_job


app = FastAPI()


config.load_incluster_config()
batch_api = client.BatchV1Api()



@app.get("/health")
def health():
    return {"status": "ok"}

# Llama.cpp job request
class LlamaRequest(BaseModel):
    prompt: str = "Explain why the sky is blue in three sentences."
    hf_repo: str = "ggml-org/Qwen3.5-0.8B-GGUF"
    hf_file: str = "Qwen3.5-0.8B-Q4_0.gguf"



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


@app.get("/jobs/{job_name}")
def get_job(job_name: str):
    try:
        job = batch_api.read_namespaced_job(
            name=job_name,
            namespace="llm",
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
        "namespace": job.metadata.namespace,
        "status": status,
    }