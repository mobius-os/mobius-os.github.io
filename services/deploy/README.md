# Möbius Launch Deployment

This stack is the org-owned deployment source for the launcher at
`https://mobius.you` and `https://mobius.page`. The static Pages site can stay
on `mobius-os.github.io`; this service owns only the dynamic launcher.

## Prerequisites

- A VPS or equivalent host with Docker and Docker Compose.
- Root `A` or `AAAA` records for `mobius.you` and `mobius.page` pointing to
  this host.
- Optional `www` records for both domains pointing to the same host.
- Google and Railway OAuth apps with both callback hosts registered.

This Compose stack binds ports 80 and 443. If the target machine already runs a
different Caddy container on those ports, either move the Möbius DNS records to
a dedicated host or fold these site blocks into the existing edge proxy during
the cutover.

## Deploy

```bash
git clone https://github.com/mobius-os/mobius-os.github.io.git
cd mobius-os.github.io/services/deploy
cp .env.example .env
# Edit .env with production ACME and OAuth values.
docker compose up -d --build
docker compose logs -f caddy mobius-launch
```

Operational checks:

```bash
curl https://mobius.you/health
curl https://mobius.page/health
```

## OAuth Callbacks

Register all of these URLs so users can stay on either host:

- Google: `https://mobius.you/auth/google/callback`
- Google alternate: `https://mobius.page/auth/google/callback`
- Railway: `https://mobius.you/railway/callback`
- Railway alternate: `https://mobius.page/railway/callback`

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

```bash
cd mobius-os.github.io/services/deploy
git pull
docker compose up -d --build
```

For a launcher-only change:

```bash
docker compose up -d --build mobius-launch caddy
```
