# Cloud Web access

Use the [inherited deployment guide](DEPLOY_EN.md) for Docker, services, and scheduling, or the [Vietnam deployment runbook](RUNBOOK_DOCKER_RENDER.md) for SSI V3.

Keep the app bound to loopback for a local reverse proxy. For intentional external binding in a direct deployment, set `WEBUI_HOST=0.0.0.0` and select `WEBUI_PORT` before restarting. For Compose, check the host-side `API_PORT` mapping and the container listener. Use `python main.py --serve-only` to serve Web and API. The schedule path is separate.

Restrict inbound access and enable administrator authentication for remote use. Configure TLS and proxy trust at the reverse proxy. See [Security and secrets](SECURITY_AND_SECRETS.md) and [.env.example](../.env.example) for the supported settings.

If the page is unreachable, verify the process, container port mapping, host firewall, and cloud security group in that order. Check `/api/health` for readiness. After rebuilding, verify the running image and served Web assets before investigating browser cache.
