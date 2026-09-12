from kubernetes import client
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

    return job



def extract_llama_answer(log: str | bytes) -> str:
    # Kubernetes/client configuration may give us bytes
    if isinstance(log, bytes):
        log = log.decode("utf-8", errors="replace")

    # Remove everything through the end of the thinking section
    if "[End thinking]" in log:
        log = log.rsplit("[End thinking]", 1)[1]

    # Remove llama.cpp timing information and anything after it
    if "[ Prompt:" in log:
        log = log.split("[ Prompt:", 1)[0]

    return log.strip()


