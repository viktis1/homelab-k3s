# GPU
This directory contains the components used to run GPU workloads in the cluster.

## Architecture
GPU worksloads have been chosen to run as short-lived Kubernetes jobs, since requests are sparse. Requests are submitted through the `gpu-orchestrator`, which creates Jobs in the corresponding workload namespace and returns their results. 

- `gpu-orchestrator`: FastAPI service for creating, tracking, and retrieving results from GPU Jobs. Interface is available at https://gpu-orchestrator.viktor.cloud/docs.
- `llm`: Kubernetes resources and job templates for running llama.cpp inference with quantized GGUF models from Hugging Face.

The LLM job accepts a Hugging Face repository and model file, so the model can be selected per request rather than being fixed in the cluster configuration.

## TODO

- [ ] Improve monitoring of short-lived GPU Jobs with higher-frequency container metrics and DCGM GPU metrics on GPU-node.
- [ ] Make the orchestrator/job interface generic before adding additional GPU workloads such as TTS.
