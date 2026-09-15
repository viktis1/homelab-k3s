from kubernetes import client
from pydantic import BaseModel
from fastapi.responses import PlainTextResponse
import yaml
import codecs


JOB_TYPE = "llama"
NAMESPACE = "llm"


class Request(BaseModel):
    prompt: str = "Explain why the sky is blue in three sentences."
    hf_repo: str = "bartowski/Qwen3.8-27B-GGUF"
    hf_file: str = "Qwen3.8-27B-Q5_K_S.gguf"


def build_job(
    core_api: client.CoreV1Api,
    request: Request,
    job_name: str,
):
    # Get the llama.cpp job template
    config_map = core_api.read_namespaced_config_map(
        name="llm-job-template",
        namespace=NAMESPACE,
    )
    job = yaml.safe_load(
        config_map.data["llm.job.yaml"]
    )
    # Alter the job spec to include the prompt and model
    container = next(
        container
        for container in job["spec"]["template"]["spec"]["containers"]
        if container.get("name") == "llama"
    )

    container["args"] = [
        "--hf-repo",
        request.hf_repo,
        "--hf-file",
        request.hf_file,
        "--prompt",
        request.prompt,
        "--single-turn",
    ]

    return job


def read_result(
    core_api: client.CoreV1Api,
    pod,
    job_name: str,
):
    log = core_api.read_namespaced_pod_log(
        name=pod.metadata.name,
        namespace=NAMESPACE,
        container="llama",
    )

    answer = extract_llama_answer(log)

    return PlainTextResponse(answer)





#----------------------------------------------------------------------------
#------------------------ Helper functions ----------------------------------
#----------------------------------------------------------------------------


def extract_llama_answer(log: str | bytes) -> str:
    if isinstance(log, bytes):
        log = log.decode("utf-8", errors="replace")
    
    log = codecs.escape_decode(
        log.encode("utf-8")
    )[0].decode("utf-8")


    if "[End thinking]" in log:
        log = log.rsplit("[End thinking]", 1)[1]

    if "[ Prompt:" in log:
        log = log.split("[ Prompt:", 1)[0]

    return log.strip()