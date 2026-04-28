# Preview Environments

This project can build a pull request branch, deploy it to a dedicated preview server, and post the live URL back on the PR for visual review.

## How it works

1. GitHub Actions checks out the PR head commit and builds the app image.
2. The image is streamed over SSH to a preview server.
3. The server starts one container per PR and writes a per-PR Caddy snippet.
4. The workflow posts a sticky PR comment with the preview URL.
5. When the PR closes, the workflow removes the container, Caddy snippet, and per-PR working directory.

## Security model

The preview deployment is intentionally isolated from the rest of the host:

- each PR gets its own container
- each PR gets its own MongoDB container and database directory
- the container runs with `no-new-privileges`
- Linux capabilities are dropped
- the filesystem is read-only except for small tmpfs scratch areas
- the preview app gets its own Docker network
- the preview services should be preview-only, not production services

That isolation reduces the blast radius if a branch contains malicious or broken code. It does not replace server hardening. The preview server should still be dedicated to previews or otherwise tightly firewalled.

If you want the strongest isolation, run the preview app and its supporting services
inside a dedicated Docker network that is not shared with production workloads.

## One-time server setup

Install and configure:

- Docker
- Caddy, or another reverse proxy that can route per-PR hostnames
- SSH access for GitHub Actions
- wildcard DNS for the preview subdomain, such as `*.preview.example.com`

Create a server environment file, by default:

- `/etc/mielenosoitukset-preview.env`

It should define the app secrets and preview-only service endpoints, for example:

- `PREVIEW_SECRET_KEY`
- `PREVIEW_MAIL_SERVER`
- `PREVIEW_MAIL_USERNAME`
- `PREVIEW_MAIL_PASSWORD`
- `PREVIEW_CDN_BASE_URL`
- optional `PREVIEW_REDIS_HOST`, `PREVIEW_REDIS_PORT`, `PREVIEW_REDIS_DB`
- optional `PREVIEW_DEFAULT_LOCALE`, `PREVIEW_DEFAULT_TIMEZONE`
- optional `PREVIEW_MONGO_SOURCE_URI` and `PREVIEW_MONGO_SOURCE_DB` if you want the preview MongoDB to be seeded from an existing server database

The app will render a per-PR YAML config file from those values and use it through `CONFIG_YAML_PATH`. The runtime config always points the app to its own local MongoDB container at `mongodb://mongo:27017`.

If you enable the optional seeding step, the deploy script will:

1. read from the source MongoDB URI without modifying it
2. dump the chosen source database
3. restore it into the isolated preview MongoDB container

That keeps preview data separated from production data and makes branch testing easier.

Configure Caddy to import the generated snippets directory, for example:

```caddy
import /etc/caddy/previews/*.caddy
```

## GitHub secrets

Add these repository secrets:

- `PREVIEW_SSH_PRIVATE_KEY`

Add these repository variables:

- `PREVIEW_SSH_HOST`
- `PREVIEW_SSH_USER`
- `PREVIEW_DOMAIN`
- `PREVIEW_ENV_FILE`
- `PREVIEW_BASE_DIR`
- `PREVIEW_SNIPPETS_DIR`
- `PREVIEW_RELOAD_CMD`

The helper script `scripts/setup_preview_environment.sh` can print the values you need,
or apply them directly if `gh` is already authenticated.

## Operational notes

- The workflow only deploys same-repository pull requests. Forks are skipped because the preview server needs secrets.
- Each PR gets a separate database name inside its own preview MongoDB container, so it does not share data with other previews.
- The preview config disables chat, background jobs, the email worker, and the panic thread by default to keep previews lighter and safer.
- If the preview server needs stricter isolation, keep the backing services on the same dedicated Docker network and do not reuse production containers.
