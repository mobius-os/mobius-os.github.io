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
CURATED_REPOS = ["app-news"]  # add new curated app repos here
GRID_SLOTS = 4  # total cards shown on apps/index.html (rest are "Coming soon")

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
    r = client.get(url, headers=HEADERS, timeout=20.0)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def fetch_app(client: httpx.Client, repo: str) -> dict:
    """Fetch manifest + GitHub metadata for one repo, returning a render-ready dict."""
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
    app["manifest_json"] = json.dumps(manifest, indent=2, ensure_ascii=False)
    app["github"] = {
        "stars": repo_meta.get("stargazers_count"),
        "last_commit": last_commit,
        "discussions_count": discussions_count,
    }
    return app


def render(env: Environment, apps: list[dict]) -> list[Path]:
    """Render each per-app page + the index. Returns the list of files written."""
    written: list[Path] = []
    APPS_DIR.mkdir(parents=True, exist_ok=True)

    app_tpl = env.get_template("app.html.j2")
    for app in apps:
        out = APPS_DIR / f"{app['id']}.html"
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
