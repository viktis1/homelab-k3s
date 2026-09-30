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


## self-developed Applications
- `gpu/gpu_orchestrator`: small CPU-only service responsible for creating GPU Kubernetes Jobs.
- `gpu/llm`: GPU jobs that can run selected models from Hugging Face.
- `gpu/tts`: GPU jobs that can run VoxCPM2 for TTS.
- `create-ringtone`: Orchestrator that establishes an outbound connection to GCS so the ringtones can be created outside the LAN.  

There are interesting docs in all the self-developed applications. The reader is encouraged to go into the folders and check those out for more technical descriptions of how the apps work.

# Secret Management
Secrets in this project are handled via SOPS using age keys (inspired by [this](https://oneuptime.com/blog/post/2026-03-02-how-to-set-up-sops-for-encrypted-secrets-on-ubuntu/view)). To set this up request permission from creator. Install SOPS and AGE if necessary:
```bash
# Download SOPS (I use version 3.13.3)
wget https://github.com/getsops/sops/releases/download/v3.13.3/sops-v3.13.3.linux.amd64 -O /tmp/sops
sudo install -m 755 /tmp/sops /usr/local/bin/sops
# Download age
sudo apt install age
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt
# set an environment variable for SOPS by adding this to ~/.bashrc or ~/.zshrc: 
export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
```
To get access to new secrets, your public key must be inserted into the .sops.yaml. To get access to already-created secrets someone with access to the encrypted secrets must update access to keys in the repository
```bash
sops updatekeys secret1.yaml
sops updatekeys secret2.yaml
....
```
To encrypt a secret in a file with sops, see the sops tutorial https://getsops.io/docs/usage/common-operations/. All of the kubernetes manifests currently rely on you decrypting the secrets into a non-encrypted version to upload them to kubernetes: 
```bash
sops decrypt cloudflare/resources/cloudflare.secret.sops.yaml > cloudflare/resources/cloudflare.secret.yaml
```