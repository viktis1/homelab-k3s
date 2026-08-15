from typing import Any
from kubernetes import client
from pathlib import Path
import yaml



def build_llama_job(prompt:str, hf_repo:str, hf_file:str):
    # Get the job template from the LLM namespace
    core_api = client.CoreV1Api()
    config_map = core_api.read_namespaced_config_map(
        name="llm-job-template",
        namespace="llm",
    )
    job = yaml.safe_load(config_map.data["llm.job.yaml"])

    # Get the container spec for the llama-cpp container
    container = next(
        c for c in job["spec"]["template"]["spec"]["containers"]
        if c.get("name") == "llama"
    )
    container["args"] = [
        "--hf-repo",
        hf_repo,
        "--hf-file",
        hf_file,
        "--single-turn",
        "--prompt",
        prompt,
        "--ctx-size",
        "4096",
        "--n-gpu-layers",
        "all",
    ]

    # Create the job in the LLM namespace
    api = client.BatchV1Api()
    return api.create_namespaced_job(
        namespace="llm",
        body=job,
    )