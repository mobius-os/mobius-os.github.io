# Möbius Launch

Möbius Launch is the small bridge between a signed-in user and their
Railway-owned Möbius deployment. It is served publicly at
`https://mobius.you` and `https://mobius.page`; `https://mobius.you` is the
canonical URL.

## What It Stores

- User identity from sign-in: email, name, provider id, and avatar URL when available.
- Encrypted Railway OAuth tokens so the launcher can create, reconcile, and delete deployments.
- Deployment identifiers and links: Railway project, service, environment, volume, public URL, recovery URL, selected resource caps, and short provisioning events/errors.

## What It Does Not Store

- Möbius conversations, files, apps, databases, or agent activity.
- Railway passwords or Google passwords.
- Historical CPU/RAM/disk/network samples.
- Billing history or exact spend totals.

Workspace choices, deployment status, and resource metrics are fetched live from Railway when the dashboard needs them.

## Deployment

Use the org-owned stack in `../deploy`. The launcher defaults to root-mounted
URLs and `https://mobius.you`, so local or legacy prefixed deployments must set
`APP_BASE_PATH` and `PUBLIC_BASE_URL` explicitly.

The public runtime exposes:

- `/health` for liveness.
- `/version` for source repository, source path, deployed commit, deploy mode,
  and public host configuration.

## Railway Billing Notes

Railway's docs currently describe:

- A free trial with a one-time $5 grant for up to 30 days, available without a credit card.
- Hobby at $5/month, including $5 of resource usage each billing cycle.
- Usage-based compute pricing for CPU, RAM, volume storage, and network egress.
- Hard usage limits that take workloads offline to prevent additional usage.

Useful references:

- https://docs.railway.com/pricing/free-trial
- https://docs.railway.com/pricing/faqs
- https://docs.railway.com/pricing/plans
- https://docs.railway.com/pricing/cost-control
- https://docs.railway.com/observability/metrics
- https://docs.railway.com/networking/public-networking
- https://docs.railway.com/deployments/reference
- https://docs.railway.com/integrations/api

## ServiceInstance Race

Railway's `serviceDomainCreate` can return `ServiceInstance not found` immediately after `templateDeployV2` creates the project and service. The public docs do not document that exact error string as a user-facing condition, so the launcher treats it as an inferred readiness race: wait for `serviceInstance(serviceId, environmentId)` to appear, then retry or reuse the domain.
