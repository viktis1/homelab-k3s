# Homelab K3s
This repository contains the Kubernetes manifests used to manage my home K3s cluster.

## Motivation and underlying system
The project started as a way to learn more about the infrastructure surrounding machine learning while making use of local compute instead of expensive cloud CPUs, GPUs, and storage.

The cluster runs on a single gaming computer using **Proxmox VE** as the hypervisor. Four VMs form the K3s cluster:
- one small server node
- two CPU worker nodes
- one GPU worker node with an RTX 4090

The separation into VMs is primarily intended to provide a small environment for experimenting with Kubernetes concepts while still running on a single physical machine.

The GPU node is used for workloads such as quantized LLM and TTS inference.


## Cluster infrastructure
The repository contains manifests for the main services supporting the cluster:

- `cert-manager`: issues TLS certificates for HTTPS connections.
- `MetalLB`: assigns external LAN IPs to selected services.
- `Traefik-dashboard`: configuration for the Traefik ingress routes that connect exposed MetalLB IPs to the appropriate services and a dashboard. 
- `Tailscale`: provides remote access to the cluster through a Tailscale subnet route (I have CGNAT)
- `Headlamp`: provides a web interface for inspecting Kubernetes resources.
- `metrics-server`: provides resource usage metrics to Kubernetes.
- `monitoring`: Prometheus and Grafana for monitoring and visualization.


## Applications
- `adguard`: DNS-level ad blocking for the local network. Mid results...
- `gpu/gpu_orchestrator`: small CPU-only service responsible for creating GPU Kubernetes Jobs.
- `gpu/llm`: GPU jobs that can run selected models from Hugging Face.

GPU workloads are intentionally treated as batch jobs rather than permanently running inference services. The orchestrator provides a common entry point for submitting these jobs, with the intention of supporting additional GPU workloads such as TTS in the future.