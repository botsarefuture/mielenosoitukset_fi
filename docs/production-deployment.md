# Production deployment

Every commit pushed to `main` triggers `.github/workflows/production-deploy.yml`.
The workflow connects with a dedicated SSH credential and invokes
`deploy/production_deploy.sh` on the server with the exact merged commit SHA.

The server script serializes deployments, refuses stale SHAs, fast-forwards the
production checkout, installs dependencies only when `requirements.txt`
changed, and asks systemd/Gunicorn for a graceful reload. Existing workers keep
serving while replacements start. Both the server and GitHub Actions verify the
public `/health` endpoint.

Configure the GitHub `production` environment with:

- variables `PRODUCTION_SSH_HOST` and `PRODUCTION_SSH_USER`
- secrets `PRODUCTION_SSH_PRIVATE_KEY` and `PRODUCTION_SSH_KNOWN_HOSTS`

The production SSH key should be dedicated to this workflow and constrained on
the server with `deploy/production_ssh_entrypoint.sh` as its forced command. Do
not reuse a personal administrative key. The installed `/root/update-moso.sh`
should be kept in sync with `deploy/production_deploy.sh`.
