import json
import yaml

from kubernetes import client
from pydantic import BaseModel


JOB_TYPE = "lid"
NAMESPACE = "lid"

    
class Request(BaseModel):
    audio_url: str = ""


def build_job(
    core_api: client.CoreV1Api,
    request: Request,
    job_name: str,
):
    config_map = core_api.read_namespaced_config_map(
        name="lid-firered-job-template",
        namespace=NAMESPACE,
    )

    job = yaml.safe_load(
        config_map.data["lid-firered.job.yaml"]
    )

    container = next(
        container
        for container in job["spec"]["template"]["spec"]["containers"]
        if container["name"] == "firered-lid"
    )

    container["args"] = [
        "--model-dir",
        "/models/FireRedLID",
        "--audio",
        request.audio_url,
    ]

    return job


def read_result(core_api, pod, job_name):
    response = core_api.read_namespaced_pod_log(
        name=pod.metadata.name,
        namespace=NAMESPACE,
        container="firered-lid",
        _preload_content=False,
    )

    return json.loads(response.data)