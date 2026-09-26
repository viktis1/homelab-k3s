# Considerations for exposing the create-ringtone application publically
I wanted to expose my API endpoint via an identity-aware proxy, to ensure that authentication was handled by a cloud provider. Since the K8s server is behind CGNAT it does not have a publically routable IP address. Therefore, the server has to have and outbound connection to the provider. I did not want to buy a VM on their cloud to make this work. I first explored the big 3 cloud providers: GCP/AWS/Azure to see if they lived up to these criterias

- **[GCP IAP](https://docs.cloud.google.com/iap/docs/enabling-on-prem-howto)** and **[AWS Verified Access](https://medium.com/awsfullstack/how-to-expose-internal-applications-securely-using-aws-verified-access-no-vpn-required-4c5d7dcab0e3)**
    - authentication is handled by GCP / AWS
    - authorization could be defined via their control system
    - The connection between the server and cloud service requires network reachability of the server...
- **[Microsoft Entra Application Proxy](https://learn.microsoft.com/en-us/entra/identity/app-proxy/application-proxy-secure-api-access)**
    - authentication is handled by Azure
    - authorization could be defined via their control system
    - The connection between the server and cloud service is created via outbound connection
    - The proxy requires Microsoft Entra ID P1 or P2 licensing to create the connection...

Since none of the big cloud providors were able to satisfy the requirements, I decided to use cloudflare, a content delivery network platform with [a good pricing model](https://www.cloudflare.com/plans/?utm_source=chatgpt.com) for small businesses. In general, I have tried to keep my APIs limited to the big 3 cloud providers, but cloudflare satisfied the exact requirements via their **Cloudflare Tunnel + Cloudflare Access**. The application itself remains private. Cloudflare provides the public ingress point, verifies the user's identity and access policy, and only then forwards the request through the pre-established tunnel to the private FastAPI service.


# Guide to do it
https://developers.cloudflare.com/tunnel/guides/kubernetes/

Create access control for the new application in cloudflare: https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/?utm_source=chatgpt.com
