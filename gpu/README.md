# GPU
This directory contains the components used to run GPU workloads in the cluster.

## Architecture
GPU worksloads have been chosen to run as short-lived Kubernetes jobs, since requests are sparse. Requests are submitted through the `gpu-orchestrator`, which creates Jobs in the corresponding workload namespace and returns their results. 

- `gpu-orchestrator`: FastAPI service for creating, tracking, and retrieving results from GPU Jobs. Interface is available at https://gpu-orchestrator.viktor.cloud/docs.
- `llm`: Kubernetes resources and job templates for running llama.cpp inference with quantized GGUF models from Hugging Face.
- `tts`: Kubernetes resources and job templates for running VoxCPM2 from my computer.

There is currently no help in passing the right arguments to the gpu-orchestrator when creating the different jobs, so please use the examples below as a draft:
JOB_TYPE: LLAMA
    {"prompt": "Whatever you want to write here", 
     "hf_repo": "bartowski/Qwen3.8-27B-GGUF"
     "hf_file": "Qwen3.8-27B-Q5_K_S.gguf"}
JOB_TYPE: TTS 
    {"prompt": "Whatever you want read out loud"}
    

## TODO

- [ ] Make the orchestrator/job interface better and easier-to-use (IT SHOULDN'T REQUIRE DOCS TO RUN THE WORKLOADS!!!).
