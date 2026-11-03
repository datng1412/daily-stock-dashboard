# Deployment compatibility reference

> Frozen. Use the [inherited deployment guide](DEPLOY_EN.md) or the [Vietnam Docker and Render runbook](RUNBOOK_DOCKER_RENDER.md) for maintained deployment instructions.

The documentation regression suite checks these non-root Compose commands at this path.

```bash
docker-compose -f ./docker/docker-compose.yml exec -u dsa stock-analyzer bash
docker-compose -f ./docker/docker-compose.yml exec -u dsa stock-analyzer python main.py --no-notify
```
