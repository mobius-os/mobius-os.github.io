# Möbius Launch Deployment

This stack is the org-owned deployment source for the launcher at
`https://www.mobius.you` and `https://www.mobius.page`. The bare domains
redirect to their matching `www` host; this service owns only the dynamic
launcher.

`mobius.Caddyfile` is the org-owned edge fragment for the public launcher
domains. On a shared VPS, the host's edge proxy serves that fragment while
continuing to serve unrelated hosts from their own repos' fragments.

## Prerequisites

- A VPS or equivalent host with Docker and Docker Compose.
- Root `A` or `AAAA` records for `mobius.you` and `mobius.page` pointing to
  this host.
- `www` records for both domains pointing to the same host.
- Google and Railway OAuth apps with both `www` callback hosts registered.

There are two supported deployment modes:

- **Dedicated host:** this repo owns Caddy and binds ports 80 and 443.
- **Shared VPS:** the host's shared edge proxy owns ports 80 and 443 and
  serves this repo's `mobius.Caddyfile` fragment, while the launcher runs as
  its own Compose project on the external `edge-launch` Docker network.

## Deploy

### Dedicated Host

```bash
git clone https://github.com/mobius-os/mobius-os.github.io.git
cd mobius-os.github.io/services/deploy
cp .env.example .env
# Edit .env with production ACME and OAuth values.
MOBIUS_LAUNCH_GIT_SHA="$(git -C ../.. rev-parse --short=12 HEAD)" docker compose up -d --build
docker compose logs -f caddy mobius-launch
```

### Shared VPS

Use this mode when the host runs a shared edge proxy (the `edge` repo) that
owns ports 80 and 443. The launcher runs in the `mobius-launch` Compose
project on the external `edge-launch` network, and `deploy-shared-vps.sh`
installs `mobius.Caddyfile` into the edge via its `edgectl` (checkout
location overridable with `EDGE_DIR`, default `~/projects/edge`). The edge
enforces per-producer hostname ownership, validates the assembled config
before reload, and keeps the previous fragment on any failure.

```bash
git clone https://github.com/mobius-os/mobius-os.github.io.git
cd mobius-os.github.io/services/deploy
cp .env.example .env
# Edit .env with production OAuth values. Keep MOBIUS_LAUNCH_VOLUME pointed at
# the existing production volume if migrating from another Compose project.
./deploy-shared-vps.sh
```

When migrating the current shared VPS from the older `deploy` Compose project,
keep `MOBIUS_LAUNCH_VOLUME=deploy_mobius_launch_data`, move traffic to the new
`mobius-launch` project, and only remove the stopped legacy launcher container.
Do not remove the `deploy_mobius_launch_data` volume.

Operational checks:

```bash
curl https://www.mobius.you/health
curl https://www.mobius.page/health
curl https://www.mobius.you/version
```

## OAuth Callbacks

Register all of these URLs so users can stay on either primary host:

- Google: `https://www.mobius.you/auth/google/callback`
- Google alternate: `https://www.mobius.page/auth/google/callback`
- Railway: `https://www.mobius.you/railway/callback`
- Railway alternate: `https://www.mobius.page/railway/callback`

Keeping the old bare-domain callbacks registered is harmless during migration,
but new sessions should be generated on the `www` hosts.

## Data Migration

The launcher stores account/session metadata, encrypted Railway OAuth tokens,
deployment records, and provisioning events in the `mobius_launch_data` Docker
volume. It does not store Möbius instance files, chats, or app data; those live
inside each user's Railway project.

Back up the old volume before changing DNS:

```bash
docker run --rm \
  -v deploy_mobius_launch_data:/from:ro \
  -v "$PWD":/backup \
  alpine tar czf /backup/mobius_launch_data.tgz -C /from .
```

Restore it on the new host before starting the launcher:

```bash
docker volume create deploy_mobius_launch_data
docker run --rm \
  -v deploy_mobius_launch_data:/to \
  -v "$PWD":/backup \
  alpine sh -c 'tar xzf /backup/mobius_launch_data.tgz -C /to'
```

Then start the stack and move the `mobius.you` / `mobius.page` DNS records.

## Updating

Dedicated host:

```bash
cd mobius-os.github.io/services/deploy
git pull
MOBIUS_LAUNCH_GIT_SHA="$(git -C ../.. rev-parse --short=12 HEAD)" docker compose up -d --build
```

Shared VPS:

```bash
cd mobius-os.github.io/services/deploy
git pull
./deploy-shared-vps.sh
```

`deploy-shared-vps.sh` reinstalls the fragment on every run; `edgectl`
validates and reloads the edge proxy only when needed.
