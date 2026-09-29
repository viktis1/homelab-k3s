terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5"
    }
  }
}

provider "cloudflare" {
  api_token = var.api_token
}



# Create a Cloudflare tunnel
resource "cloudflare_zero_trust_tunnel_cloudflared" "homelabk3s" {
  account_id = var.account_id
  name       = "homelabk3s"
  config_src = "cloudflare"
}
output "tunnel_id" {
  value = cloudflare_zero_trust_tunnel_cloudflared.homelabk3s.id
}

# Inside the Cloudflare tunnel, link subdomains to the service in the cluster
resource "cloudflare_zero_trust_tunnel_cloudflared_config" "homelabk3s" {
  account_id = var.account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.homelabk3s.id
  config = {
    ingress = [
      {
        hostname = "gpu-orchestrator.${var.domain}"
        service  = "http://gpu-orchestrator.gpu-orchestrator:8000"
      },
      {
        hostname = "create-ringtone.${var.domain}"
        service  = "http://create-ringtone-orchestrator.create-ringtone:8000"
      },
      {
        service = "http_status:404"
      }
    ]
  }
}

# Make sure that the subdomains are pointing to the Cloudflare tunnel
resource "cloudflare_dns_record" "gpu_orchestrator" {
  zone_id = var.zone_id
  name    = "gpu-orchestrator"
  content = "${cloudflare_zero_trust_tunnel_cloudflared.homelabk3s.id}.cfargotunnel.com"
  type    = "CNAME"
  ttl     = 1
  proxied = true
}
resource "cloudflare_dns_record" "create_ringtone" {
  zone_id = var.zone_id
  name    = "create-ringtone"
  content = "${cloudflare_zero_trust_tunnel_cloudflared.homelabk3s.id}.cfargotunnel.com"
  type    = "CNAME"
  ttl     = 1
  proxied = true
}

# Read tunnel credential for cloudflared
data "cloudflare_zero_trust_tunnel_cloudflared_token" "homelabk3s" {
  account_id = var.account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.homelabk3s.id
}



output "tunnel_token" {
  value     = data.cloudflare_zero_trust_tunnel_cloudflared_token.homelabk3s.token
  sensitive = true
}