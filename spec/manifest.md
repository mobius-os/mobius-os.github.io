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
  "static_assets": {
    "index.html": "build/index.html",
    "static/js/main.js": "build/static/js/main.js"
  },
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

- **`id`** — the app's slug in Möbius. Charset `a-z 0-9 - _`; it
  must not start with `-` or `_`, and must not be purely numeric
  (bare integers are reserved for the `/data/apps/<id>` storage
  path). A single character is allowed. The id is the app's own
  choice and need not equal the `app-<repo>` name — for example
  `app-workout` ships id `gym`.
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

### Optional appearance + capability flags

- **`theme_color`** — `#RRGGBB` hex hinting the app's preferred
  theme/accent colour to the shell. Anything outside `#RRGGBB` is
  ignored by the installer.
- **`background_color`** — `#RRGGBB` hex hinting the app's preferred
  background colour to the shell. Same `#RRGGBB` rule.
- **`embeds_agent`** — `true` when the app embeds the Möbius chat
  surface (via the embedded-agent component). The store badges such
  apps as agent-powered. Apps that set this typically also request
  `permissions.chat_log_access`.

### Static assets

```json
"static_assets": {
  "index.html": "build/index.html",
  "static/js/main.js": "build/static/js/main.js",
  "static/media/logo.png": "build/static/media/logo.png"
}
```

Prebuilt apps can declare files to copy into
`/data/apps/<slug>/static`. They are served at both
`/app-assets/<slug>/...` and `/app-assets/by-id/<id>/...`.

- Use an **object** when source and served paths differ:
  destination path → repo source path.
- Use an **array** when the repo source path and served destination
  path are identical.
- Paths must be repo-relative, must not start with `/`, and must not
  escape with `..`.
- Updates are declarative: files previously owned by
  `static_assets` but no longer declared are removed. Unrelated files
  under `static/` are preserved.

For bundled React/Vite/Webpack apps, include every HTML, CSS, JS,
font, media, and source-map file referenced by the build output.
CSS `url(...)` references stay relative to the served CSS file, so
declare the destination paths exactly as the browser will request
them.

### Permissions

```json
"permissions": {
  "cross_app_access": "none" | "read" | "write",
  "share_with_apps":  "none" | "read" | "write",
  "chat_log_access":  "none" | "summary" | "full"
}
```

- **`cross_app_access`** — what this app can do to OTHER apps'
  storage. `none` (default), `read`, or `write`.
- **`share_with_apps`** — what OTHER apps can do to THIS app's
  storage. Same set. Effective right between apps =
  `min(caller.cross_app_access, target.share_with_apps)`.
- **`chat_log_access`** — how much of the owner's chat history the
  app may read. `none` (default), `summary`, or `full`. This is a
  separate value space from the storage read/write/none ladder.
  `full` is accepted in the manifest so the column round-trips, but
  the read API rejects it until a concrete consumer ships.

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

- **`default`** — optional initial cron expression. Omit it for an
  on-demand-only job such as a Build button that runs `build.sh`.
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

- **`imports`** — bare specifiers the app uses that are already in
  Möbius's `app-frame.html` importmap (no fetch cost). The canonical
  set is the `imports` enum in
  [`mobius.schema.json`](mobius.schema.json); as of v1.0 that is
  `react`, `react-dom`, `react-dom/client`, `react/jsx-runtime`,
  `recharts`, `date-fns`, `three`, `three/addons/`, `pdfjs-dist`,
  `codemirror`, and `katex`. Anything not on that list isn't bundled
  — declare it under `esm_deps` instead.
- **`esm_deps`** — libraries the app loads via
  `import('https://esm.sh/<pkg>')`. The store UI surfaces these so
  users know the app pulls from a third-party CDN on first load.

## Install lifecycle

When the user installs an app:

1. **Fetch manifest** — installer GETs `mobius.json` from the
   declared URL (raw.githubusercontent.com for the curated case).
2. **Validate** — the backend validates the manifest before
   installing (`install._validate_manifest`): required fields,
   `id`/path charsets, permission and cron-expression value spaces.
   This page's `mobius.schema.json` mirrors those rules so you can
   check a manifest before you publish.
3. **Pre-install confirm** — Möbius shows the user: name, version,
   icon, requested permissions, optional cron preview ("runs daily
   at 10:00 UTC"), declared `esm_deps`. User taps Install.
4. **POST to /api/apps/install** — the backend fetches `entry`,
   compiles it, creates or updates the App row, writes the editable
   source tree, seeds storage, uploads the icon, and registers cron
   inside one transaction with filesystem rollback.
5. **Schedule (if any)** — if `schedule.default` is present, the
   installer registers the recurring cron entry for `schedule.job`.
   If only `schedule.job` is present, the job is bundled for explicit
   in-app `run-job` actions but no recurring cron is installed.
6. **Done** — app appears in drawer next time the user opens it
   (or immediately, via `chat_updated` SSE).

## Versioning + updates

- Patch bumps (`1.0.0 → 1.0.1`) — store offers a one-click update.
  Installer PATCHes `jsx_source`; app rebuilds via the
  file-watcher.
- Minor bumps — same as patch.
- Major bumps — store warns the user and shows a diff link
  before applying. User must explicitly accept.

The store mini-app maintains its own per-installed-app version map
at `/api/storage/apps/<store_id>/installed-versions.json` (keyed by
catalog id, or by manifest id for paste-a-URL installs). Installed
identity is the backend's canonical manifest URL key:
`<manifest-base>#manifest-id=<manifest.id>`. Slug is routing only,
so user-built apps and store-installed apps can coexist even when
their names collide.

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

The schema mirrors the backend's `install._validate_manifest` rules,
so a manifest that passes here is the one Möbius accepts at install
time.
