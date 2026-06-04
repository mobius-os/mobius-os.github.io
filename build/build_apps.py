#!/usr/bin/env python3
"""Regenerate per-app pages and the catalog index from each curated repo's manifest.

Curated repos live under github.com/mobius-os/app-<id>. For each one we fetch:
- raw mobius.json (the source of truth)
- /repos/<owner>/<repo> for stars + last commit date
- /repos/<owner>/<repo>/discussions/categories for discussion presence

Adding a new curated app: append its repo slug (e.g. "app-notes") to CURATED_REPOS.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

ORG = "mobius-os"
CURATED_REPOS = ["app-news", "app-atlas", "app-workout", "app-latex", "app-dreaming", "app-mind", "app-notes"]  # add new curated app repos here
GRID_SLOTS = 4  # total cards shown on apps/index.html (rest are "Coming soon")
PAGE_SLUG_OVERRIDES = {
    # The manifest id is still `gym` for install/storage compatibility,
    # but the public app page should use the product name.
    "gym": "workout",
}

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
APPS_DIR = ROOT / "apps"

# GitHub API token — optional; raises rate limit from 60/hr to 5000/hr.
GH_TOKEN = os.environ.get("GITHUB_TOKEN")
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "mobius-os-site-builder"}
if GH_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GH_TOKEN}"


def _get_json(client: httpx.Client, url: str) -> Any:
    """GET + JSON-decode. Returns None on 404 so callers can treat absence as a soft miss."""
    r = client.get(url, headers=HEADERS, timeout=20.0, follow_redirects=True)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def fetch_app(client: httpx.Client, repo: str) -> dict:
    """Fetch manifest + GitHub metadata for one repo, returning a render-ready dict."""
    local_manifest = ROOT.parent / repo / "mobius.json"
    if local_manifest.exists():
        manifest = json.loads(local_manifest.read_text(encoding="utf-8"))
    else:
        manifest = _get_json(
            client, f"https://raw.githubusercontent.com/{ORG}/{repo}/main/mobius.json"
        )
        if manifest is None:
            raise RuntimeError(f"{repo}: mobius.json missing on main")

    repo_meta = _get_json(client, f"https://api.github.com/repos/{ORG}/{repo}") or {}

    # Discussions: the categories endpoint 404s if discussions are disabled.
    discussions_count: int | None = None
    if repo_meta.get("has_discussions"):
        cats = _get_json(
            client, f"https://api.github.com/repos/{ORG}/{repo}/discussions/categories"
        )
        discussions_count = len(cats) if isinstance(cats, list) else 0

    pushed_at = repo_meta.get("pushed_at")
    last_commit = None
    if pushed_at:
        last_commit = datetime.fromisoformat(pushed_at.replace("Z", "+00:00")).date().isoformat()

    app = dict(manifest)
    app["repo"] = repo
    app["page_slug"] = PAGE_SLUG_OVERRIDES.get(app["id"], app["id"])
    app["manifest_json"] = json.dumps(manifest, indent=2, ensure_ascii=False)
    app["github"] = {
        "stars": repo_meta.get("stargazers_count"),
        "last_commit": last_commit,
        "discussions_count": discussions_count,
        "open_issues": repo_meta.get("open_issues_count"),
    }
    # If the manifest declares an icon, expose a full raw URL so the
    # template can render an <img> instead of a letter placeholder. We
    # don't HEAD-check the URL here — a missing icon.png 404s in the
    # browser and the template's letter fallback is just a Jinja `if`.
    icon = manifest.get("icon")
    app["icon_url"] = (
        f"https://raw.githubusercontent.com/{ORG}/{repo}/main/{icon}"
        if icon else None
    )

    # Surface a small set of capability badges directly so the template
    # doesn't need to dig into manifest fields. The offline badge is
    # nuanced — `offline_capable: true` on the App row only means the
    # SW caches the frame + module + storage outbox queues writes; it
    # does NOT mean every interactive surface works offline. Per-app
    # accuracy comes from OFFLINE_BADGE_OVERRIDES below.
    app["badges"] = []
    if manifest.get("offline_capable"):
        override = OFFLINE_BADGE_OVERRIDES.get(manifest.get("id"))
        app["badges"].append(override or "Works offline")
    sched = manifest.get("schedule") or {}
    if sched.get("default"):
        # Cron expression → very-short human label. Best-effort; falls
        # back to the raw cron expression if the shape is unfamiliar.
        app["badges"].append(_human_cron(sched["default"]))
    perms = manifest.get("permissions") or {}
    if perms.get("cross_app_access") and perms["cross_app_access"] != "none":
        app["badges"].append(
            f"Reads other apps ({perms['cross_app_access']})"
        )
    return app


# Per-app override for the offline badge so each card sets honest
# expectations. "Works offline" is reserved for apps where ALL
# interactive surfaces function without the network. Apps that need
# the network for their headline action ship a narrower badge.
OFFLINE_BADGE_OVERRIDES = {
    # news: cached reports survive offline reloads, but new reports
    # come from a server-side cron. The viewer reads offline; new
    # content needs network.
    "news": "Reads offline",
    # latex: editor + math preview + file tree work offline, the
    # persistent agent chat is the only online-required surface. The
    # headline interaction (chatting with the agent to edit .tex)
    # requires network.
    "latex": "Edits offline",
    # dreaming: report viewer reads offline; the nightly cron that
    # generates new dreams is server-side.
    "dreaming": "Reads offline",
    # atlas / gym have no server-side dependency for their
    # headline interaction; "Works offline" is accurate. Leave them
    # to fall back to the default.
}


def _human_cron(expr: str) -> str:
    """Cheap pretty-printer for the cron forms our curated apps use.

    Intentionally omits the time — every Möbius user picks the
    hour/minute per-install in the app's own Settings tab, so the
    catalog badge would lie about the schedule being fixed.
    """
    parts = expr.split()
    if len(parts) != 5:
        return f"Runs `{expr}`"
    _minute, _hour, dom, mon, dow = parts
    if dom == "*" and mon == "*" and dow == "*":
        return "Runs daily"
    return f"Runs `{expr}`"


def render(env: Environment, apps: list[dict]) -> list[Path]:
    """Render each per-app page + the index. Returns the list of files written."""
    written: list[Path] = []
    APPS_DIR.mkdir(parents=True, exist_ok=True)

    app_tpl = env.get_template("app.html.j2")
    for app in apps:
        out = APPS_DIR / f"{app['page_slug']}.html"
        out.write_text(app_tpl.render(app=app), encoding="utf-8")
        written.append(out)

    coming_soon = max(0, GRID_SLOTS - len(apps))
    idx_tpl = env.get_template("index.html.j2")
    idx_out = APPS_DIR / "index.html"
    idx_out.write_text(
        idx_tpl.render(apps=apps, coming_soon_count=coming_soon, generated_on=date.today().isoformat()),
        encoding="utf-8",
    )
    written.append(idx_out)
    return written


def main() -> int:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html"]),
        keep_trailing_newline=True,
    )
    with httpx.Client() as client:
        apps = [fetch_app(client, repo) for repo in CURATED_REPOS]

    written = render(env, apps)
    for p in written:
        print(f"wrote {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
