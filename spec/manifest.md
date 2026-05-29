# mobius.json — Möbius app manifest

A Möbius app is a directory (typically a git repo) with a
`mobius.json` at its root. The manifest declares everything the
Möbius runtime needs to install the app: the entry point, the
icon, optional storage seeds, optional cron schedule, runtime
library imports, and the permissions the app requests.

Apps that follow this format can be installed:
- via the **App Store** mini-app (curated apps under `mobius-os/`)
- via **paste-a-URL** install (any public manifest URL)
- via **bootstrap** at first container boot (the app-store
  mini-app itself is installed this way)

## Schema (v1.0)

```json
{
  "id": "news",
  "name": "News",
  "version": "1.0.0",
  "description": "Daily AI-curated news digest, configurable categories.",
  "author": "mobius-os",
  "license": "MIT",
  "homepage": "https://github.com/mobius-os/app-news",
  "icon": "icon.png",
  "entry": "index.jsx",
  "permissions": {
    "cross_app_access": "none",
    "share_with_apps": "none"
  },
  "storage_seeds": {
    "prompt.md": "prompt.md",
    "schedule.json": { "hour": 10, "minute": 0, "categories": ["world", "tech", "business"] }
  },
  "schedule": {
    "default": "0 10 * * *",
    "user_configurable": true,
    "job": "fetch.sh"
  },
  "runtime": {
    "imports": ["react", "react-dom", "recharts"],
    "esm_deps": []
  }
}
```

## Field reference

### Required

- **`id`** — kebab-case identifier, must match the repo name's
  `app-<id>` portion (e.g. `news` for `app-news`). Becomes the
  app's slug in Möbius.
- **`name`** — human-facing display name (used in drawer + store UI).
- **`version`** — semver. Patch = code-only (hot rebase), minor =
  backwards-compatible new schema fields, major = breaking changes
  that need user attention.
- **`description`** — one-line user-facing summary.
- **`entry`** — relative path to the JSX entry file (always
  `index.jsx` in practice; the field is here so the spec can grow
  to multi-file apps later).

### Recommended

- **`author`** — GitHub user or org.
- **`license`** — SPDX identifier (`MIT`, `Apache-2.0`, …).
- **`homepage`** — URL where users can learn more / file issues.
- **`icon`** — relative path to a PNG. Server resizes to 1024×1024,
  center-square-crops if not square. Skip this field and the
  Möbius default letter-icon is used.

### Permissions

```json
"permissions": {
  "cross_app_access": "none" | "read" | "write",
  "share_with_apps":  "none" | "read" | "write"
}
```

- **`cross_app_access`** — what this app can do to OTHER apps'
  storage. `none` (default), `read`, or `write`.
- **`share_with_apps`** — what OTHER apps can do to THIS app's
  storage. Same set. Effective right between apps =
  `min(caller.cross_app_access, target.share_with_apps)`.

The store UI shows requested permissions on the install confirm
screen. Owner tokens bypass both checks.

### Storage seeds

```json
"storage_seeds": {
  "prompt.md": "prompt.md",
  "schedule.json": { "hour": 10, "minute": 0 }
}
```

Maps storage paths (under `/api/storage/apps/<slug>/`) to either:

- **a string** — a path to a file in the repo. The file's bytes
  are PUT to the storage path verbatim.
- **a JSON literal** — the value is JSON-encoded and written.

Used for default content the app's UI assumes is present on first
launch (default prompts, default schedules, sample data).

### Schedule

```json
"schedule": {
  "default": "0 10 * * *",
  "user_configurable": true,
  "job": "fetch.sh"
}
```

If present, the installer registers a cron entry that invokes
`/data/apps/<slug>/<job>` at the cron-expression's cadence.

- **`default`** — initial cron expression.
- **`user_configurable`** — if `true`, the installer also seeds
  `schedule.json` in storage (with `{hour, minute}` parsed from
  `default`) and arranges a `sync-cron.sh` polling script so the
  user can change the time from within the app UI.
- **`job`** — relative path to the shell script that runs at each
  trigger. Repo bundles it; installer copies to
  `/data/apps/<slug>/<job>` with `chmod +x`.

### Runtime

```json
"runtime": {
  "imports": ["react", "react-dom", "recharts"],
  "esm_deps": ["marked"]
}
```

- **`imports`** — libraries the app uses that are already in
  Möbius's `app-frame.html` importmap (no fetch cost). Currently:
  `react`, `react-dom`, `react/jsx-runtime`, `recharts`,
  `date-fns`, `three`, plus `lucide-react`, `framer-motion`
  if present.
- **`esm_deps`** — libraries the app loads via
  `import('https://esm.sh/<pkg>')`. The store UI surfaces these so
  users know the app pulls from a third-party CDN on first load.

## Install lifecycle

When the user installs an app:

1. **Fetch manifest** — installer GETs `mobius.json` from the
   declared URL (raw.githubusercontent.com for the curated case).
2. **Validate** — manifest is JSON-Schema-checked against
   `mobius.schema.json` (TBD; ticket 057).
3. **Pre-install confirm** — Möbius shows the user: name, version,
   icon, requested permissions, optional cron preview ("runs daily
   at 10:00 UTC"), declared `esm_deps`. User taps Install.
4. **POST to /api/apps/** — creates the DB row with `jsx_source`
   from `entry`, `cross_app_access`, `share_with_apps`. Server
   assigns numeric id + slug.
5. **Storage seeds** — installer PUTs each entry in
   `storage_seeds` to `/api/storage/apps/<slug>/<path>`.
6. **Icon upload** — if `icon` declared, PUT `icon.png` bytes to
   `/api/apps/{id}/icon`.
7. **Schedule (if any)** — installer copies the job script to
   `/data/apps/<slug>/<job>` and runs
   `/app/scripts/init-cron-scaffold.sh <slug> "<schedule.default>"`
   to register the cron entry.
8. **Done** — app appears in drawer next time the user opens it
   (or immediately, via `chat_updated` SSE).

## Versioning + updates

- Patch bumps (`1.0.0 → 1.0.1`) — store offers a one-click update.
  Installer PATCHes `jsx_source`; app rebuilds via the
  file-watcher.
- Minor bumps — same as patch.
- Major bumps — store warns the user and shows a diff link
  before applying. User must explicitly accept.

The on-disk `/data/apps/<slug>/version.txt` records the installed
version. The store mini-app polls each installed app's `mobius.json`
on its homepage URL to detect available updates.

## Future fields (reserved, not yet implemented)

- **`screenshots`** — array of relative paths to screenshot PNGs;
  the store website uses these on the per-app page.
- **`tags`** — categorization for store search/filter.
- **`requires`** — provider/SDK requirements (e.g. `"providers":
  ["claude", "codex"]`).
- **`platform_deps`** — Python / npm packages a platform-class
  manifest declares (for the `mobius` repo update flow, ticket 056).

## Validating your manifest

```bash
npx ajv-cli validate -s mobius.schema.json -d mobius.json
```

(JSON Schema publication is tracked under ticket 057.)
