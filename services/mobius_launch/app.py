import base64
import hashlib
import html
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import closing
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from flask import Flask, Response, g, make_response, redirect, render_template_string, request, send_from_directory
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


DATA_DIR = os.environ.get("DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "mobius_launch.sqlite3")
SECRET_PATH = os.path.join(DATA_DIR, "session-secret.txt")
APP_BASE_PATH = os.environ.get("APP_BASE_PATH", "").rstrip("/")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://mobius.you").rstrip("/")
PUBLIC_CANONICAL_URL = os.environ.get("PUBLIC_CANONICAL_URL", "https://mobius.you").rstrip("/")
PUBLIC_HOSTS = {
    host.strip().lower()
    for host in os.environ.get("PUBLIC_HOSTS", "mobius.page,mobius.you").split(",")
    if host.strip()
}
PUBLIC_BASE_HOST = urllib.parse.urlparse(PUBLIC_BASE_URL).netloc.lower()
if PUBLIC_BASE_HOST:
    PUBLIC_HOSTS.add(PUBLIC_BASE_HOST)

RAILWAY_AUTH_URL = os.environ.get(
    "RAILWAY_AUTH_URL", "https://backboard.railway.com/oauth/auth"
)
RAILWAY_TOKEN_URL = os.environ.get(
    "RAILWAY_TOKEN_URL", "https://backboard.railway.com/oauth/token"
)
RAILWAY_ME_URL = os.environ.get(
    "RAILWAY_ME_URL", "https://backboard.railway.com/oauth/me"
)
RAILWAY_GRAPHQL_URL = os.environ.get(
    "RAILWAY_GRAPHQL_URL", "https://backboard.railway.com/graphql/v2"
)
RAILWAY_CLIENT_ID = os.environ.get("RAILWAY_CLIENT_ID", "").strip()
RAILWAY_CLIENT_SECRET = os.environ.get("RAILWAY_CLIENT_SECRET", "").strip()
RAILWAY_REDIRECT_URI = os.environ.get(
    "RAILWAY_REDIRECT_URI", f"{PUBLIC_BASE_URL}/railway/callback"
).strip()
RAILWAY_OAUTH_SCOPES = os.environ.get(
    "RAILWAY_OAUTH_SCOPES", "openid email profile offline_access workspace:member"
).strip()
RAILWAY_TEMPLATE_URL = os.environ.get(
    "RAILWAY_TEMPLATE_URL",
    "https://railway.com/deploy/xVMuX9?referralCode=cERpKq&utm_medium=integration&utm_source=template&utm_campaign=generic",
).strip()
RAILWAY_TEMPLATE_CODE = os.environ.get("RAILWAY_TEMPLATE_CODE", "xVMuX9").strip()
RAILWAY_REFERRAL_CODE = os.environ.get("RAILWAY_REFERRAL_CODE", "cERpKq").strip()
# Step 1 of onboarding sends the user here to create their Railway account. The
# referral has to attach at signup: Railway silently ignores referralCode on the
# OAuth authorize endpoint, and its ToS prompt fires during signup, not mid-OAuth
# (see the "reducing OAuth onboarding friction" feedback thread). Defaults to the
# canonical referral link derived from RAILWAY_REFERRAL_CODE.
# `or` (not the get() default) so a set-but-empty RAILWAY_SIGNUP_URL="" from an
# env-file still falls back to the derived link instead of rendering href="".
RAILWAY_SIGNUP_URL = os.environ.get("RAILWAY_SIGNUP_URL", "").strip() or (
    f"https://railway.com?referralCode={RAILWAY_REFERRAL_CODE}"
    if RAILWAY_REFERRAL_CODE
    else "https://railway.com"
)
PROVISIONING_STALE_SECONDS = int(os.environ.get("PROVISIONING_STALE_SECONDS", "900"))
GOOGLE_AUTH_URL = os.environ.get("GOOGLE_AUTH_URL", "https://accounts.google.com/o/oauth2/v2/auth")
GOOGLE_TOKEN_URL = os.environ.get("GOOGLE_TOKEN_URL", "https://oauth2.googleapis.com/token")
GOOGLE_USERINFO_URL = os.environ.get(
    "GOOGLE_USERINFO_URL", "https://openidconnect.googleapis.com/v1/userinfo"
)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI", f"{PUBLIC_BASE_URL}/auth/google/callback"
).strip()
ALLOW_PROTOTYPE_EMAIL_LOGIN = os.environ.get(
    "ALLOW_PROTOTYPE_EMAIL_LOGIN", "true"
).strip().lower() in {"1", "true", "yes", "on"}
MOBIUS_IMAGE_REF = os.environ.get("MOBIUS_IMAGE_REF", "").strip()
MOBIUS_SOURCE_REPO = os.environ.get("MOBIUS_SOURCE_REPO", "mobius-os/mobius").strip()
MOBIUS_SOURCE_BRANCH = os.environ.get("MOBIUS_SOURCE_BRANCH", "main").strip()
MOBIUS_SERVICE_NAME = os.environ.get("MOBIUS_SERVICE_NAME", "mobius").strip()
MOBIUS_SERVICE_PORT_RAW = os.environ.get("MOBIUS_SERVICE_PORT", "").strip()
MOBIUS_SERVICE_PORT = int(MOBIUS_SERVICE_PORT_RAW) if MOBIUS_SERVICE_PORT_RAW else None
MOBIUS_VOLUME_MOUNT_PATH = os.environ.get("MOBIUS_VOLUME_MOUNT_PATH", "/data").strip()
MOBIUS_DEFAULT_VOLUME_SIZE_GB = os.environ.get(
    "MOBIUS_DEFAULT_VOLUME_SIZE_GB",
    os.environ.get("MOBIUS_DEFAULT_VOLUME_SIZE", "2"),
).strip()
MOBIUS_VOLUME_SIZE_OPTIONS_GB = os.environ.get(
    "MOBIUS_VOLUME_SIZE_OPTIONS_GB", "2,5,10,20"
).strip()
MOBIUS_DEPLOY_ENVIRONMENT = os.environ.get("MOBIUS_DEPLOY_ENVIRONMENT", "production").strip()
MOBIUS_LAUNCH_SOURCE_REPO = os.environ.get(
    "MOBIUS_LAUNCH_SOURCE_REPO", "mobius-os/mobius-os.github.io"
).strip()
MOBIUS_LAUNCH_SOURCE_PATH = os.environ.get(
    "MOBIUS_LAUNCH_SOURCE_PATH", "services/mobius_launch"
).strip()
MOBIUS_LAUNCH_GIT_SHA = (
    os.environ.get("MOBIUS_LAUNCH_GIT_SHA", "unknown").strip() or "unknown"
)
MOBIUS_LAUNCH_IMAGE_REF = os.environ.get("MOBIUS_LAUNCH_IMAGE_REF", "").strip()
MOBIUS_LAUNCH_DEPLOY_MODE = os.environ.get("MOBIUS_LAUNCH_DEPLOY_MODE", "unknown").strip()

os.makedirs(DATA_DIR, exist_ok=True)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
LOGO_FILENAME = "moebius.png"
PREVIEW_FILENAME = "app-store.png"


def static_asset_version(filename):
    try:
        with open(os.path.join(STATIC_DIR, filename), "rb") as file:
            return hashlib.sha256(file.read()).hexdigest()[:12]
    except OSError:
        return str(int(time.time()))


LOGO_VERSION = static_asset_version(LOGO_FILENAME)
PREVIEW_VERSION = static_asset_version(PREVIEW_FILENAME)

app = Flask(__name__)


class RailwayAPIError(RuntimeError):
    pass


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_info():
    return {
        "service": "mobius-launch",
        "source_repo": MOBIUS_LAUNCH_SOURCE_REPO,
        "source_path": MOBIUS_LAUNCH_SOURCE_PATH,
        "git_sha": MOBIUS_LAUNCH_GIT_SHA,
        "image_ref": MOBIUS_LAUNCH_IMAGE_REF or "unknown",
        "deploy_mode": MOBIUS_LAUNCH_DEPLOY_MODE or "unknown",
        "public_base_url": PUBLIC_BASE_URL,
        "public_canonical_url": PUBLIC_CANONICAL_URL,
        "public_hosts": sorted(PUBLIC_HOSTS),
    }


def load_secret():
    if os.environ.get("MOBIUS_LAUNCH_SECRET"):
        return os.environ["MOBIUS_LAUNCH_SECRET"]
    if os.path.exists(SECRET_PATH):
        with open(SECRET_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    secret = secrets.token_urlsafe(48)
    with open(SECRET_PATH, "w", encoding="utf-8") as f:
        f.write(secret)
    os.chmod(SECRET_PATH, 0o600)
    return secret


APP_SECRET = load_secret()
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days; enforced server-side in current_user


def _derive_key(info):
    # Domain-separated key derivation so a leak/bug in one purpose (session
    # forgery) does not also compromise the other (decrypting stored Railway
    # tokens). The info tag makes each derived key independent of the others.
    return hashlib.sha256(APP_SECRET.encode("utf-8") + b"|" + info).digest()


# Timed serializer: the session token itself carries a signed timestamp, so it
# expires server-side (unlike the cookie max_age, which a client can ignore).
serializer = URLSafeTimedSerializer(APP_SECRET, salt="mobius-launch-session")
oauth_state_serializer = URLSafeTimedSerializer(
    APP_SECRET, salt="mobius-launch-railway-oauth"
)
google_state_serializer = URLSafeTimedSerializer(
    APP_SECRET, salt="mobius-launch-google-oauth"
)
fernet = Fernet(base64.urlsafe_b64encode(_derive_key(b"token-encryption")))


def connect_db():
    # WAL + a generous busy_timeout so the request-scoped reader and the
    # background provisioning threads (each on their own connection) don't trip
    # "database is locked" when they contend on the same file.
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma journal_mode=WAL")
    conn.execute("pragma busy_timeout=30000")
    return conn


def db():
    if "db" not in g:
        g.db = connect_db()
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@app.get("/favicon.png")
def favicon():
    return send_from_directory(STATIC_DIR, LOGO_FILENAME, mimetype="image/png", max_age=300)


@app.get("/moebius.png")
def moebius_logo():
    return send_from_directory(STATIC_DIR, LOGO_FILENAME, mimetype="image/png", max_age=86400)


@app.get("/workspace-preview.png")
def workspace_preview():
    return send_from_directory(STATIC_DIR, PREVIEW_FILENAME, mimetype="image/png", max_age=86400)


@app.before_request
def csrf_guard():
    # Defense in depth on top of SameSite=Lax cookies: reject any state-changing
    # request the browser marks as coming from another site. Same-origin form
    # posts carry Sec-Fetch-Site: same-origin; a cross-site attack page carries
    # cross-site. Non-browser clients (curl) send no header and pass through.
    # This also closes login-CSRF, since /login is a POST.
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if request.headers.get("Sec-Fetch-Site") == "cross-site":
            return Response("Forbidden", status=403)


def ensure_column(conn, table, column, ddl):
    rows = conn.execute(f"pragma table_info({table})").fetchall()
    if column not in {row[1] for row in rows}:
        try:
            conn.execute(f"alter table {table} add column {ddl}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise


def init_db():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.executescript(
            """
            create table if not exists users (
              id text primary key,
              email text not null,
              name text not null,
              avatar_url text,
              auth_provider text not null,
              auth_provider_subject text not null,
              created_at text not null,
              last_login_at text not null
            );

            create table if not exists railway_connections (
              id text primary key,
              user_id text not null,
              railway_sub text,
              railway_email text,
              railway_name text,
              railway_picture text,
              railway_workspace_id text,
              railway_workspace_name text,
              connected_mode text not null,
              granted_scopes text,
              token_type text,
              token_expires_at integer,
              access_token_ciphertext text,
              refresh_token_ciphertext text,
              last_error text,
              created_at text not null,
              updated_at text not null,
              foreign key(user_id) references users(id)
            );

            create table if not exists mobius_instances (
              id text primary key,
              user_id text not null,
              railway_connection_id text,
              display_name text not null,
              handle text not null,
              status text not null,
              railway_project_id text not null,
              railway_environment_id text not null,
              railway_service_id text not null,
              railway_volume_id text not null,
              railway_domain text not null,
              public_url text not null,
              recovery_url text not null,
              auth_mode text not null,
              image_ref text not null,
              source_kind text,
              source_ref text,
              volume_size_gb text,
              railway_project_name text,
              railway_workspace_name text,
              current_step text,
              last_error text,
              last_deployment_id text,
              last_seen_at text,
              created_at text not null,
              updated_at text not null,
              foreign key(user_id) references users(id)
            );

            create table if not exists instance_events (
              id text primary key,
              instance_id text not null,
              level text not null,
              message text not null,
              created_at text not null,
              foreign key(instance_id) references mobius_instances(id)
            );
            """
        )
        ensure_column(conn, "users", "avatar_url", "avatar_url text")
        for column, ddl in [
            ("railway_name", "railway_name text"),
            ("railway_picture", "railway_picture text"),
            ("token_type", "token_type text"),
            ("token_expires_at", "token_expires_at integer"),
            ("access_token_ciphertext", "access_token_ciphertext text"),
            ("refresh_token_ciphertext", "refresh_token_ciphertext text"),
            ("last_error", "last_error text"),
            ("cached_plan", "cached_plan text"),
            ("deploy_blocked", "deploy_blocked text"),
            ("plan_checked_at", "plan_checked_at text"),
            ("railway_workspaces_json", "railway_workspaces_json text"),
        ]:
            ensure_column(conn, "railway_connections", column, ddl)
        for column, ddl in [
            ("source_kind", "source_kind text"),
            ("source_ref", "source_ref text"),
            ("volume_size_gb", "volume_size_gb text"),
            ("tier", "tier text"),
            ("cpu", "cpu text"),
            ("memory_gb", "memory_gb text"),
            ("memory_mb", "memory_mb text"),
            ("plan_label", "plan_label text"),
            ("railway_project_name", "railway_project_name text"),
            ("railway_workspace_name", "railway_workspace_name text"),
            ("current_step", "current_step text"),
            ("last_error", "last_error text"),
            ("last_deployment_id", "last_deployment_id text"),
            ("provision_token", "provision_token text"),
        ]:
            ensure_column(conn, "mobius_instances", column, ddl)
        conn.execute(
            "update mobius_instances set display_name = ? where display_name = ?",
            ("My Möbius", "My Mobius"),
        )
        conn.commit()


init_db()


def h(value):
    return html.escape(str(value or ""), quote=True)


def path(route=""):
    if not route:
        return APP_BASE_PATH + "/"
    if not route.startswith("/"):
        route = "/" + route
    return APP_BASE_PATH + route


def logo_url():
    return f"{path('/moebius.png')}?v={LOGO_VERSION}"


def preview_url():
    return f"{path('/workspace-preview.png')}?v={PREVIEW_VERSION}"


def current_public_base_url():
    forwarded_host = (request.headers.get("X-Forwarded-Host") or "").split(",")[0].strip()
    host = (forwarded_host or request.host or "").split(":", 1)[0].lower()
    if host.startswith("www."):
        host = host[4:]
    if host in PUBLIC_HOSTS:
        return f"https://{host}"
    return PUBLIC_BASE_URL


def google_redirect_uri():
    return current_public_base_url() + path("/auth/google/callback")


def railway_redirect_uri():
    return current_public_base_url() + path("/railway/callback")


def encrypt_secret(value):
    if not value:
        return None
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value):
    if not value:
        return None
    return fernet.decrypt(value.encode("utf-8")).decode("utf-8")


def google_oauth_configured():
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def email_login_enabled():
    # The passwordless email fallback is a prototype-only convenience. The
    # moment a real identity provider (Google) is configured we refuse it
    # regardless of the env flag, so the unauthenticated login path cannot be
    # used to impersonate a real account.
    return ALLOW_PROTOTYPE_EMAIL_LOGIN and not google_oauth_configured()


def current_user():
    raw = request.cookies.get("mobius_launch_session")
    if not raw:
        return None
    try:
        payload = serializer.loads(raw, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    user = db().execute(
        "select * from users where id = ?", (payload.get("user_id"),)
    ).fetchone()
    return user


def require_user():
    user = current_user()
    if user is None:
        return None
    return user


def set_session(resp, user_id):
    token = serializer.dumps({"user_id": user_id})
    resp.set_cookie(
        "mobius_launch_session",
        token,
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=SESSION_MAX_AGE,
        path=APP_BASE_PATH or "/",
    )
    return resp


def clear_session(resp):
    resp.delete_cookie("mobius_launch_session", path=APP_BASE_PATH or "/")
    return resp


def railway_oauth_configured():
    return bool(RAILWAY_CLIENT_ID and RAILWAY_CLIENT_SECRET)


def mobius_source():
    if RAILWAY_TEMPLATE_CODE:
        return "template", RAILWAY_TEMPLATE_CODE
    if MOBIUS_IMAGE_REF:
        return "image", MOBIUS_IMAGE_REF
    return "repo", MOBIUS_SOURCE_REPO


def normalize_handle(value, fallback="mobius"):
    raw = (value or fallback or "mobius").strip().lower()
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    raw = re.sub(r"[^a-z0-9-]+", "-", raw)
    raw = re.sub(r"-+", "-", raw).strip("-")
    if len(raw) < 3:
        raw = f"{raw or 'mobius'}-{secrets.token_hex(2)}"
    return raw[:40].strip("-")


def get_connection(user_id):
    return db().execute(
        """
        select * from railway_connections
        where user_id = ?
          and connected_mode = 'oauth'
        order by updated_at desc
        limit 1
        """,
        (user_id,),
    ).fetchone()


def list_instances(user_id):
    return db().execute(
        """
        select * from mobius_instances
        where user_id = ?
          and status != 'deleted'
        order by created_at desc
        """,
        (user_id,),
    ).fetchall()


def short_date(value):
    if not value:
        return "never"
    return str(value).replace("T", " ")[:16]


def format_volume_gb(value):
    try:
        size = float(value)
    except (TypeError, ValueError):
        return ""
    if size.is_integer():
        return str(int(size))
    return f"{size:.2f}".rstrip("0").rstrip(".")


def coerce_volume_size_gb(value, fallback=None):
    if value is None:
        return fallback
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    if not match:
        return fallback
    size = float(match.group(0))
    if size < 0.5 or size > 5000:
        return fallback
    if size.is_integer():
        return int(size)
    return size


def default_volume_size_gb():
    return coerce_volume_size_gb(MOBIUS_DEFAULT_VOLUME_SIZE_GB, 2) or 2


def volume_size_options_gb():
    default = default_volume_size_gb()
    options = [default]
    for item in re.split(r"[,\s]+", MOBIUS_VOLUME_SIZE_OPTIONS_GB):
        size = coerce_volume_size_gb(item)
        if size and size not in options:
            options.append(size)
    return options


def normalize_volume_size_gb(value):
    size = coerce_volume_size_gb(value)
    options = volume_size_options_gb()
    if size in options:
        return format_volume_gb(size)
    return format_volume_gb(options[0])


def volume_size_mb(value):
    size = coerce_volume_size_gb(value, default_volume_size_gb()) or default_volume_size_gb()
    return int(round(float(size) * 1024))


def volume_size_label(value):
    size = coerce_volume_size_gb(value, default_volume_size_gb()) or default_volume_size_gb()
    return f"{format_volume_gb(size)} GB"


def format_gb_label(value):
    try:
        gb = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if gb <= 0:
        return "0"
    if 0.95 <= gb < 1.05:
        return "1 GB"
    if gb < 1:
        return f"{gb * 1024:.0f} MB"
    if gb < 10:
        return f"{gb:.2f}".rstrip("0").rstrip(".") + " GB"
    return f"{gb:.1f}".rstrip("0").rstrip(".") + " GB"


def format_cpu_label(value):
    try:
        cpu = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if cpu < 0.01:
        return f"{cpu:.4f} vCPU"
    if cpu < 1:
        return f"{cpu:.2f} vCPU"
    return f"{cpu:.1f}".rstrip("0").rstrip(".") + " vCPU"


def percent_label(used, total, decimals=0):
    try:
        used = float(used)
        total = float(total)
    except (TypeError, ValueError):
        return ""
    if total <= 0:
        return ""
    value = min(999, (used / total) * 100)
    if decimals:
        return f"{value:.{decimals}f}".rstrip("0").rstrip(".") + "%"
    return f"{value:.0f}%"


def volume_size_select_options(selected=None):
    selected_size = normalize_volume_size_gb(selected)
    return "\n".join(
        f"""<option value="{format_volume_gb(size)}" {'selected' if format_volume_gb(size) == selected_size else ''}>{format_volume_gb(size)} GB</option>"""
        for size in volume_size_options_gb()
    )


PLAN_LIMITS = {
    "trial": {
        "max_cpu": 2,
        "max_memory_mb": 1024,
        "max_volume_gb": 0.5,
        "memory_options_mb": [256, 512, 1024],
        "volume_options_gb": [0.5],
    },
    "free": {
        "max_cpu": 1,
        "max_memory_mb": 512,
        "max_volume_gb": 0.5,
        "memory_options_mb": [256, 512],
        "volume_options_gb": [0.5],
    },
    "hobby": {
        "max_cpu": 8,
        "max_memory_mb": 8192,
        "max_volume_gb": 5,
        "memory_options_mb": [512, 1024, 2048, 4096, 8192],
        "volume_options_gb": [0.5, 1, 2, 5],
    },
    "pro": {
        "max_cpu": 24,
        "max_memory_mb": 24576,
        "max_volume_gb": 1000,
        "memory_options_mb": [1024, 2048, 4096, 8192, 16384, 24576],
        "volume_options_gb": [2, 5, 10, 20, 50, 100, 250, 500, 1000],
    },
    "enterprise": {
        "max_cpu": 2400,
        "max_memory_mb": 2457600,
        "max_volume_gb": 5000,
        "memory_options_mb": [4096, 8192, 16384, 32768, 65536, 131072, 262144],
        "volume_options_gb": [5, 20, 50, 100, 250, 500, 1000, 5000],
    },
    "unknown": {
        "max_cpu": 8,
        "max_memory_mb": 8192,
        "max_volume_gb": 5,
        "memory_options_mb": [512, 1024, 2048, 4096, 8192],
        "volume_options_gb": [0.5, 1, 2, 5],
    },
}


def normalize_plan_label(label):
    token = re.sub(r"[^a-z0-9]+", "_", str(label or "").lower()).strip("_")
    if token in PLAN_LIMITS:
        return token
    for known in ("enterprise", "pro", "hobby", "trial", "free"):
        if known in token:
            return known
    return "unknown"


def plan_limits(label):
    return PLAN_LIMITS.get(normalize_plan_label(label), PLAN_LIMITS["unknown"])


def plan_default_volume_gb(label):
    return min(2, plan_limits(label)["max_volume_gb"])


def memory_mb_label(value):
    try:
        mb = int(value)
    except (TypeError, ValueError):
        return ""
    if mb < 1024:
        return f"{mb} MB"
    return f"{mb // 1024} GB"


def plan_title(label):
    label = normalize_plan_label(label)
    return label.title() if label in PLAN_LIMITS and label != "unknown" else "Unknown"


def plan_cap_label(label):
    limits = plan_limits(label)
    cpu = format_cpu_label(limits["max_cpu"])
    memory = memory_mb_label(limits["max_memory_mb"])
    return f"{cpu} / {memory} RAM"


def plan_volume_select_options(label, selected=None):
    selected_size = format_volume_gb(selected or plan_default_volume_gb(label))
    return "\n".join(
        f"""<option value="{format_volume_gb(size)}" {'selected' if format_volume_gb(size) == selected_size else ''}>{format_volume_gb(size)} GB</option>"""
        for size in plan_limits(label)["volume_options_gb"]
    )


def plan_memory_select_options(label):
    options = ["""<option value="" selected>Plan maximum</option>"""]
    options.extend(
        f"""<option value="{size}">{memory_mb_label(size)}</option>"""
        for size in plan_limits(label)["memory_options_mb"]
    )
    return "\n".join(options)


def clamped_int(value, fallback, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(fallback)
    return max(minimum, min(maximum, parsed))


def oauth_error(title, message):
    body = f"""
    <main class="shell narrow">
      <section class="panel">
        <div class="section">
          <div class="brand block">
            <img class="mark" src="{logo_url()}" alt="">
            <div>
              <h1>{h(title)}</h1>
              <p class="subtitle">{h(message)}</p>
            </div>
          </div>
          <div class="actions left">
            <a class="button primary" href="{path('/')}">Back to Möbius Launch</a>
          </div>
        </div>
      </section>
    </main>
    """
    resp = make_response(render(body), 400)
    resp.delete_cookie("railway_oauth_state", path=APP_BASE_PATH or "/")
    return resp


def compact_api_error(error):
    if isinstance(error, bytes):
        error = error.decode("utf-8", errors="replace")
    try:
        data = json.loads(error)
        if isinstance(data, dict):
            message = data.get("error_description") or data.get("message") or data.get("error")
            if message:
                return str(message)[:360]
            return json.dumps(data)[:360]
    except (TypeError, ValueError):
        pass
    return str(error)[:360]


def upsert_user(email, name, provider, provider_subject, avatar_url=None):
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("email is required")
    timestamp = now_iso()
    existing = db().execute("select * from users where email = ?", (email,)).fetchone()
    if existing:
        db().execute(
            """
            update users
            set name = ?, avatar_url = ?, auth_provider = ?,
                auth_provider_subject = ?, last_login_at = ?
            where id = ?
            """,
            (
                name or existing["name"] or email.split("@", 1)[0],
                avatar_url or existing["avatar_url"],
                provider,
                provider_subject,
                timestamp,
                existing["id"],
            ),
        )
        db().commit()
        return existing["id"]

    user_id = "user_" + uuid.uuid4().hex[:10]
    db().execute(
        """
        insert into users (
          id, email, name, avatar_url, auth_provider, auth_provider_subject,
          created_at, last_login_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            email,
            name or email.split("@", 1)[0],
            avatar_url,
            provider,
            provider_subject,
            timestamp,
            timestamp,
        ),
    )
    db().commit()
    return user_id


def oauth_form_post(url, data, client_id=None, client_secret=None):
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "mobius-launch/0.1",
    }
    if client_id and client_secret:
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {auth}"
    req = urllib.request.Request(url, data=encoded, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RailwayAPIError(
            f"OAuth request failed ({exc.code}): {compact_api_error(exc.read())}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RailwayAPIError(f"OAuth request failed: {compact_api_error(exc)}") from exc


def railway_form_post(url, data, basic_auth=True):
    if basic_auth:
        return oauth_form_post(
            url,
            data,
            client_id=RAILWAY_CLIENT_ID,
            client_secret=RAILWAY_CLIENT_SECRET,
        )
    return oauth_form_post(url, data)


def railway_get_json(url, access_token):
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "mobius-launch/0.1",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RailwayAPIError(
            f"Railway request failed ({exc.code}): {compact_api_error(exc.read())}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RailwayAPIError(f"Railway request failed: {compact_api_error(exc)}") from exc


def railway_graphql(query, access_token, variables=None):
    payload_data = {"query": query}
    if variables is not None:
        payload_data["variables"] = variables
    payload = json.dumps(payload_data).encode("utf-8")
    req = urllib.request.Request(
        RAILWAY_GRAPHQL_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "mobius-launch/0.1",
        },
        method="POST",
    )
    if access_token:
        req.add_header("Authorization", f"Bearer {access_token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RailwayAPIError(
            f"Railway request failed ({exc.code}): {compact_api_error(exc.read())}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RailwayAPIError(f"Railway request failed: {compact_api_error(exc)}") from exc
    if data.get("errors"):
        raise RailwayAPIError(compact_api_error(data["errors"]))
    return data.get("data") or {}


def exchange_railway_code(code, redirect_uri, code_verifier):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    if code_verifier:
        data["code_verifier"] = code_verifier
    return railway_form_post(RAILWAY_TOKEN_URL, data)


def fetch_railway_workspaces(access_token):
    data = railway_graphql(
        "query { me { workspaces { id name } } }",
        access_token,
    )
    me = data.get("me") or {}
    return me.get("workspaces") or []


def railway_deploy_blocked(access_token, workspace_id):
    if not workspace_id:
        return None
    try:
        data = railway_graphql(
            "query($id: String!) { resourceAccess(explicitResourceOwner: { type: WORKSPACE, id: $id }) { deployment { disallowed } project { disallowed } } }",
            access_token,
            {"id": workspace_id},
        )
        resource_access = data.get("resourceAccess")
        if not isinstance(resource_access, dict):
            return None
        deployment = resource_access.get("deployment")
        project = resource_access.get("project")
        reason = None
        if isinstance(project, dict):
            reason = project.get("disallowed")
        if not reason and isinstance(deployment, dict):
            reason = deployment.get("disallowed")
        return str(reason) if reason else None
    except (RailwayAPIError, TypeError, ValueError, KeyError):
        return None


def railway_plan_label(access_token, workspace_id):
    if not workspace_id:
        return "unknown"
    try:
        data = railway_graphql(
            "query($id: String!) { workspace(workspaceId: $id) { plan customer { isTrialing } } projects(workspaceId: $id, first: 1) { edges { node { subscriptionType expiredAt } } } }",
            access_token,
            {"id": workspace_id},
        )
        workspace = data.get("workspace") or {}
        customer = workspace.get("customer") or {}
        if customer.get("isTrialing") is True:
            return "trial"
        label = normalize_plan_label(workspace.get("plan"))
        if label != "unknown":
            return label
        projects = data.get("projects")
        edges = []
        if isinstance(projects, dict):
            edges = projects.get("edges") or []
        for edge in edges:
            node = (edge or {}).get("node") or {}
            expired_at = node.get("expiredAt")
            if expired_at:
                try:
                    expires = datetime.fromisoformat(str(expired_at).replace("Z", "+00:00"))
                    if expires < datetime.now(timezone.utc):
                        continue
                except ValueError:
                    pass
            label = normalize_plan_label(node.get("subscriptionType"))
            if label != "unknown":
                return label
        return "unknown"
    except (RailwayAPIError, TypeError, ValueError, KeyError, IndexError):
        return "unknown"


def normalize_workspaces(workspaces):
    records = []
    seen = set()
    for workspace in workspaces or []:
        if not isinstance(workspace, dict):
            continue
        workspace_id = str(workspace.get("id") or "").strip()
        if not workspace_id or workspace_id in seen:
            continue
        seen.add(workspace_id)
        name = str(workspace.get("name") or workspace_id).strip() or workspace_id
        records.append({"id": workspace_id, "name": name})
    return records


def connection_workspaces(connection):
    if connection is None:
        return []
    records = []
    try:
        records = normalize_workspaces(json.loads(connection["railway_workspaces_json"] or "[]"))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        records = []
    current_id = (connection["railway_workspace_id"] or "").strip()
    if current_id and current_id not in {workspace["id"] for workspace in records}:
        records.insert(
            0,
            {
                "id": current_id,
                "name": connection["railway_workspace_name"] or current_id,
            },
        )
    return records


def live_connection_workspaces(connection):
    records = connection_workspaces(connection)
    if connection is None:
        return records
    try:
        access_token = refresh_railway_access_token(connection, db())
        fresh = normalize_workspaces(fetch_railway_workspaces(access_token))
        if fresh:
            records = fresh
            current_id = (connection["railway_workspace_id"] or "").strip()
            if current_id and current_id not in {workspace["id"] for workspace in records}:
                records.insert(
                    0,
                    {
                        "id": current_id,
                        "name": connection["railway_workspace_name"] or current_id,
                    },
                )
    except RailwayAPIError:
        pass
    return records


def workspace_select_options(workspaces, selected_id):
    return "\n".join(
        f"""<option value="{h(workspace['id'])}" {'selected' if workspace['id'] == selected_id else ''}>{h(workspace['name'])}</option>"""
        for workspace in workspaces
    )


def save_oauth_connection(user, profile, workspaces, tokens, workspace_error=None):
    timestamp = now_iso()
    existing = get_connection(user["id"])
    workspace_records = normalize_workspaces(workspaces)
    existing_workspace_id = existing["railway_workspace_id"] if existing else ""
    workspace = next(
        (item for item in workspace_records if item["id"] == existing_workspace_id),
        workspace_records[0] if workspace_records else {},
    )
    workspaces_json = None
    refresh_token = tokens.get("refresh_token")
    refresh_ciphertext = (
        encrypt_secret(refresh_token)
        if refresh_token
        else existing["refresh_token_ciphertext"]
        if existing
        else None
    )
    expires_in = int(tokens.get("expires_in") or 3600)
    values = (
        profile.get("sub"),
        profile.get("email") or user["email"],
        profile.get("name"),
        profile.get("picture"),
        workspace.get("id"),
        workspace.get("name"),
        workspaces_json,
        "oauth",
        tokens.get("scope") or RAILWAY_OAUTH_SCOPES,
        tokens.get("token_type") or "Bearer",
        int(time.time()) + expires_in,
        encrypt_secret(tokens.get("access_token")),
        refresh_ciphertext,
        workspace_error,
        timestamp,
    )
    if existing:
            db().execute(
                """
                update railway_connections
                set railway_sub = ?, railway_email = ?, railway_name = ?, railway_picture = ?,
                    railway_workspace_id = ?, railway_workspace_name = ?, railway_workspaces_json = ?,
                    connected_mode = ?,
                    granted_scopes = ?, token_type = ?, token_expires_at = ?,
                    access_token_ciphertext = ?, refresh_token_ciphertext = ?,
                    last_error = ?, cached_plan = null, deploy_blocked = '', plan_checked_at = null,
                    updated_at = ?
            where id = ?
            """,
            values + (existing["id"],),
        )
    else:
            db().execute(
                """
                insert into railway_connections (
                  id, user_id, railway_sub, railway_email, railway_name, railway_picture,
                  railway_workspace_id, railway_workspace_name, railway_workspaces_json,
                  connected_mode, granted_scopes,
                  token_type, token_expires_at, access_token_ciphertext,
                  refresh_token_ciphertext, last_error, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
            (
                "rail_" + uuid.uuid4().hex[:10],
                user["id"],
                *values[:-1],
                timestamp,
                timestamp,
            ),
        )
    db().commit()


def refresh_railway_access_token(connection, sql_conn=None):
    expires_at = int(connection["token_expires_at"] or 0)
    access_ciphertext = connection["access_token_ciphertext"]
    if access_ciphertext and expires_at > int(time.time()) + 90:
        return decrypt_secret(access_ciphertext)

    refresh_token = decrypt_secret(connection["refresh_token_ciphertext"])
    if not refresh_token:
        raise RailwayAPIError("Railway access expired. Reconnect Railway to deploy.")

    tokens = railway_form_post(
        RAILWAY_TOKEN_URL,
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    access_token = tokens.get("access_token")
    if not access_token:
        raise RailwayAPIError("Railway did not return a refreshed access token.")

    refresh_ciphertext = encrypt_secret(tokens.get("refresh_token") or refresh_token)
    expires_in = int(tokens.get("expires_in") or 3600)
    params = (
        tokens.get("token_type") or connection["token_type"] or "Bearer",
        int(time.time()) + expires_in,
        encrypt_secret(access_token),
        refresh_ciphertext,
        now_iso(),
        connection["id"],
    )
    target = sql_conn or db()
    target.execute(
        """
        update railway_connections
        set token_type = ?, token_expires_at = ?, access_token_ciphertext = ?,
            refresh_token_ciphertext = ?, updated_at = ?
        where id = ?
        """,
        params,
    )
    target.commit()
    return access_token


def cached_plan_state(connection):
    plan_label = normalize_plan_label(connection["cached_plan"])
    return {
        "plan_label": plan_label,
        "deploy_blocked": connection["deploy_blocked"] or "",
    }


def plan_cache_fresh(connection):
    checked_at = connection["plan_checked_at"]
    if not checked_at:
        return False
    try:
        checked = datetime.fromisoformat(checked_at)
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
        return time.time() - checked.timestamp() < 300
    except (TypeError, ValueError):
        return False


def get_plan_state(connection):
    if connection is None:
        return {"plan_label": "unknown", "deploy_blocked": ""}
    cached = cached_plan_state(connection)
    if plan_cache_fresh(connection):
        return cached

    try:
        access_token = refresh_railway_access_token(connection)
        workspace_id = connection["railway_workspace_id"]
        if not workspace_id:
            return {
                "plan_label": "unknown",
                "deploy_blocked": "No authorized Railway workspace was returned. Reconnect Railway and choose a workspace.",
            }
        plan_label = railway_plan_label(access_token, workspace_id)
        deploy_blocked = railway_deploy_blocked(access_token, workspace_id) or ""
        timestamp = now_iso()
        db().execute(
            """
            update railway_connections
            set cached_plan = ?, deploy_blocked = ?, plan_checked_at = ?, updated_at = ?
            where id = ?
            """,
            (plan_label, deploy_blocked, timestamp, timestamp, connection["id"]),
        )
        db().commit()
        return {"plan_label": plan_label, "deploy_blocked": deploy_blocked}
    except Exception:
        return cached


def add_instance_event(conn, instance_id, level, message):
    conn.execute(
        """
        insert into instance_events (id, instance_id, level, message, created_at)
        values (?, ?, ?, ?, ?)
        """,
        ("evt_" + uuid.uuid4().hex[:12], instance_id, level, message, now_iso()),
    )


def update_instance(conn, instance_id, **fields):
    if not fields:
        return
    fields["updated_at"] = now_iso()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [instance_id]
    conn.execute(
        f"update mobius_instances set {assignments} where id = ?",
        values,
    )
    conn.commit()


def timestamp_age_seconds(value):
    if not value:
        return float("inf")
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return time.time() - parsed.timestamp()
    except ValueError:
        return float("inf")


def claim_provisioning(instance_id, include_creating=False):
    token = "job_" + uuid.uuid4().hex
    timestamp = now_iso()
    if include_creating:
        stale_cutoff = datetime.fromtimestamp(
            time.time() - PROVISIONING_STALE_SECONDS, timezone.utc
        ).replace(microsecond=0).isoformat()
        status_condition = "status = 'queued' or (status = 'creating' and (updated_at is null or updated_at < ?))"
        params = (token, timestamp, instance_id, stale_cutoff)
    else:
        status_condition = "status = 'queued'"
        params = (token, timestamp, instance_id)
    with closing(connect_db()) as conn:
        cur = conn.execute(
            f"""
            update mobius_instances
            set provision_token = ?, status = 'creating', current_step = 'Starting deployment',
                last_error = null, updated_at = ?
            where id = ?
              and ({status_condition})
              and status != 'deleted'
            """,
            params,
        )
        conn.commit()
        if cur.rowcount != 1:
            return None
    return token


def provisioning_row(conn, instance_id, token):
    row = conn.execute(
        "select * from mobius_instances where id = ?",
        (instance_id,),
    ).fetchone()
    if row is None:
        return None
    if row["status"] == "deleted" or row["provision_token"] != token:
        return None
    return row


def project_environment_id(access_token, project_id):
    data = railway_graphql(
        """
        query project($id: String!) {
          project(id: $id) {
            environments {
              edges {
                node { id name }
              }
            }
          }
        }
        """,
        access_token,
        {"id": project_id},
    )
    edges = (((data.get("project") or {}).get("environments") or {}).get("edges") or [])
    if not edges:
        raise RailwayAPIError("Railway created the project, but no environment was returned.")
    for edge in edges:
        node = edge.get("node") or {}
        if node.get("name") == MOBIUS_DEPLOY_ENVIRONMENT:
            return node.get("id")
    return (edges[0].get("node") or {}).get("id")


def fetch_template(code):
    data = railway_graphql(
        """
        query template($code: String!) {
          template(code: $code) {
            id
            code
            name
            serializedConfig
          }
        }
        """,
        None,
        {"code": code},
    )
    template = data.get("template") or {}
    if not template.get("id") or not template.get("serializedConfig"):
        raise RailwayAPIError(f"Railway template {code} was not found.")
    return template


def template_serialized_config(template, selected_volume_size_gb):
    # Railway returns serializedConfig as a JSON object and templateDeployV2
    # requires the OBJECT back (a stringified copy is a documented failure mode),
    # so we always return a dict, never a JSON string.
    config = template["serializedConfig"]
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except (TypeError, ValueError):
            raise RailwayAPIError("Railway template config was not valid JSON.")
    if not isinstance(config, dict):
        raise RailwayAPIError("Railway template config was not valid JSON.")
    if not selected_volume_size_gb:
        return config

    size_mb = volume_size_mb(selected_volume_size_gb)
    services = config.get("services")
    if isinstance(services, dict):
        for service in services.values():
            if not isinstance(service, dict):
                continue
            mounts = service.get("volumeMounts")
            if not isinstance(mounts, dict):
                continue
            for mount in mounts.values():
                if isinstance(mount, dict) and mount.get("mountPath") in {
                    None,
                    MOBIUS_VOLUME_MOUNT_PATH,
                }:
                    mount["sizeMB"] = size_mb
    return config


def deploy_template(access_token, template, workspace_id, volume_size_gb=None):
    # One-shot deploy: templateDeployV2 with a workspaceId (and no projectId)
    # creates the project, all template services, and the /data volume, AND
    # deploys them, returning {projectId, workflowId}. This replaces the old
    # projectCreate + templateDeployV2 + serviceInstanceDeployV2 sequence, whose
    # trailing deploy triggered a redundant second build.
    if not workspace_id:
        raise RailwayAPIError(
            "No Railway workspace was found for your account. Reconnect Railway and try again."
        )
    input_data = {
        "templateId": template["id"],
        "serializedConfig": template_serialized_config(template, volume_size_gb),
        "workspaceId": workspace_id,
    }
    data = railway_graphql(
        """
        mutation templateDeployV2($input: TemplateDeployV2Input!) {
          templateDeployV2(input: $input) {
            projectId
            workflowId
          }
        }
        """,
        access_token,
        {"input": input_data},
    )
    payload = data.get("templateDeployV2") or {}
    if not payload.get("projectId"):
        raise RailwayAPIError("Railway did not return a project id after template deploy.")
    return payload


def project_resources(access_token, project_id):
    data = railway_graphql(
        """
        query projectResources($id: String!) {
          project(id: $id) {
            id
            name
            services {
              edges {
                node { id name }
              }
            }
            volumes {
              edges {
                node {
                  id
                  name
                  volumeInstances {
                    edges {
                      node {
                        id
                        externalId
                        serviceId
                        environmentId
                        mountPath
                        state
                        sizeMB
                        currentSizeMB
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """,
        access_token,
        {"id": project_id},
    )
    project = data.get("project") or {}
    services = [edge.get("node") or {} for edge in ((project.get("services") or {}).get("edges") or [])]
    volumes = [edge.get("node") or {} for edge in ((project.get("volumes") or {}).get("edges") or [])]
    return project, services, volumes


def volume_instances(volume):
    return [
        edge.get("node") or {}
        for edge in (((volume or {}).get("volumeInstances") or {}).get("edges") or [])
    ]


def matching_volume_instance(volume, service_id=None, environment_id=None):
    instances = volume_instances(volume)
    for item in instances:
        if service_id and item.get("serviceId") != service_id:
            continue
        if environment_id and item.get("environmentId") != environment_id:
            continue
        return item
    return instances[0] if instances else {}


def volume_instance_size_gb(volume_instance):
    try:
        size_mb = float((volume_instance or {}).get("sizeMB") or 0)
    except (TypeError, ValueError):
        size_mb = 0
    return size_mb / 1024 if size_mb > 0 else None


def wait_for_template_service(access_token, project_id, timeout_seconds=300, on_wait=None):
    # Waits only for the template to REGISTER the service + volume (fast, well
    # before the image finishes building). The build itself is tracked
    # afterwards via the deployment status (see reconcile_deployment_status), so
    # a slow build no longer trips this timeout into a false "error".
    start = time.time()
    last_project = {}
    while time.time() - start < timeout_seconds:
        project, services, volumes = project_resources(access_token, project_id)
        last_project = project
        if services and volumes:
            service = next(
                (s for s in services if s.get("name") == MOBIUS_SERVICE_NAME),
                services[0],
            )
            return project, service, volumes[0]
        if on_wait:
            on_wait(int(time.time() - start))
        time.sleep(3)
    raise RailwayAPIError(
        f"Railway did not register the Möbius service and /data volume within "
        f"{timeout_seconds}s for project {last_project.get('name') or project_id}."
    )


def create_service_domain(access_token, service_id, environment_id):
    payload = {
        "serviceId": service_id,
        "environmentId": environment_id,
    }
    if MOBIUS_SERVICE_PORT is not None:
        payload["targetPort"] = MOBIUS_SERVICE_PORT
    data = railway_graphql(
        """
        mutation serviceDomainCreate($input: ServiceDomainCreateInput!) {
          serviceDomainCreate(input: $input) { id domain }
        }
        """,
        access_token,
        {"input": payload},
    )
    domain = data.get("serviceDomainCreate") or {}
    if not domain.get("domain"):
        raise RailwayAPIError("Railway did not return a service domain.")
    return domain


def service_instance_details(access_token, service_id, environment_id):
    data = railway_graphql(
        """
        query serviceInstance($serviceId: String!, $environmentId: String!) {
          serviceInstance(serviceId: $serviceId, environmentId: $environmentId) {
            id
            serviceId
            environmentId
            deletedAt
            region
            domains {
              serviceDomains { id domain }
              customDomains { id domain }
            }
            latestDeployment {
              id
              status
              url
              createdAt
              updatedAt
            }
          }
        }
        """,
        access_token,
        {"serviceId": service_id, "environmentId": environment_id},
    )
    return data.get("serviceInstance") or {}


def service_instance_domain(service_instance):
    domains = (service_instance or {}).get("domains") or {}
    for key in ("serviceDomains", "customDomains"):
        for domain in domains.get(key) or []:
            if domain.get("domain"):
                return {"id": domain.get("id") or "", "domain": domain["domain"]}
    return None


def service_instance_missing_error(exc):
    return "serviceinstance not found" in compact_api_error(exc).lower()


def user_facing_railway_error(exc):
    if service_instance_missing_error(exc):
        return "Railway is still preparing usage data. Check again in a minute."
    return compact_api_error(exc)


def create_service_domain_with_retry(access_token, service_id, environment_id, timeout_seconds=180, on_wait=None):
    start = time.time()
    last_error = None
    while time.time() - start < timeout_seconds:
        try:
            existing = service_instance_domain(
                service_instance_details(access_token, service_id, environment_id)
            )
            if existing:
                return existing
        except RailwayAPIError as exc:
            last_error = exc
            if not service_instance_missing_error(exc):
                raise

        try:
            return create_service_domain(access_token, service_id, environment_id)
        except RailwayAPIError as exc:
            last_error = exc
            if not service_instance_missing_error(exc):
                existing = service_instance_domain(
                    service_instance_details(access_token, service_id, environment_id)
                )
                if existing:
                    return existing
                raise
            if on_wait:
                on_wait(int(time.time() - start))
            time.sleep(5)

    raise RailwayAPIError(
        "Railway has not finished creating the service instance yet. "
        f"Last error: {compact_api_error(last_error)}"
    )


def set_service_limits(access_token, environment_id, service_id, cpu, memory_mb):
    containers = {}
    if cpu:
        containers["cpu"] = int(cpu)
    if memory_mb:
        containers["memoryBytes"] = int(memory_mb) * 1024 * 1024
    if not containers:
        return
    patch = {
        "services": {
            service_id: {
                "deploy": {
                    "limitOverride": {
                        "containers": containers
                    }
                }
            }
        }
    }
    railway_graphql(
        """
        mutation environmentPatchCommit($environmentId: String!, $patch: EnvironmentConfig!, $commitMessage: String) {
          environmentPatchCommit(environmentId: $environmentId, patch: $patch, commitMessage: $commitMessage)
        }
        """,
        access_token,
        {
            "environmentId": environment_id,
            "patch": patch,
            "commitMessage": "Set Möbius resource limits",
        },
    )


def latest_deployment(access_token, project_id, service_id, environment_id):
    # The most recent deployment for this service in this environment. status is
    # one of the Railway DeploymentStatus values (INITIALIZING, BUILDING,
    # DEPLOYING, SUCCESS, FAILED, CRASHED, ...). Returns {} if none yet.
    data = railway_graphql(
        """
        query latestDeployment($input: DeploymentListInput!) {
          deployments(input: $input, first: 1) {
            edges { node { id status url createdAt } }
          }
        }
        """,
        access_token,
        {
            "input": {
                "projectId": project_id,
                "serviceId": service_id,
                "environmentId": environment_id,
            }
        },
    )
    edges = ((data.get("deployments") or {}).get("edges") or [])
    return (edges[0].get("node") or {}) if edges else {}


def delete_project(access_token, project_id):
    # Best-effort teardown of a Railway project (used to clean up a failed or
    # unwanted deployment so the user is not billed for an orphan).
    railway_graphql(
        """
        mutation projectDelete($id: String!) {
          projectDelete(id: $id)
        }
        """,
        access_token,
        {"id": project_id},
    )


DEPLOY_STATUS_OK = {"SUCCESS", "SLEEPING"}
DEPLOY_STATUS_BAD = {"FAILED", "CRASHED", "REMOVED", "REMOVING", "SKIPPED"}


def mobius_app_healthy(public_url, timeout=4):
    if not public_url:
        return False
    url = public_url.rstrip("/") + "/api/health"
    req = urllib.request.Request(url, headers={"User-Agent": "MobiusLaunch/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, OSError):
        return False


def can_recover_public_link(instance):
    return bool(
        instance
        and instance["railway_project_id"]
        and instance["railway_service_id"]
        and instance["railway_environment_id"]
        and not instance["public_url"]
        and instance["status"] in {"error", "creating", "deploying"}
    )


def recover_public_link(conn, instance, access_token=None):
    if not can_recover_public_link(instance):
        return instance
    connection = conn.execute(
        "select * from railway_connections where id = ?",
        (instance["railway_connection_id"],),
    ).fetchone()
    if connection is None:
        return instance
    if access_token is None:
        access_token = refresh_railway_access_token(connection, conn)

    service_instance = service_instance_details(
        access_token,
        instance["railway_service_id"],
        instance["railway_environment_id"],
    )
    domain = service_instance_domain(service_instance)
    if domain is None:
        domain = create_service_domain_with_retry(
            access_token,
            instance["railway_service_id"],
            instance["railway_environment_id"],
            timeout_seconds=60,
        )
    deployment = (
        (service_instance or {}).get("latestDeployment")
        or latest_deployment(
            access_token,
            instance["railway_project_id"],
            instance["railway_service_id"],
            instance["railway_environment_id"],
        )
    )
    deployment_status = (deployment.get("status") or "").upper()
    if deployment_status in DEPLOY_STATUS_OK:
        if mobius_app_healthy(instance["public_url"]):
            status, step, error = "ready", "Ready", ""
        else:
            status, step, error = "deploying", "Recovery online; Möbius is still starting", ""
    elif deployment_status in DEPLOY_STATUS_BAD:
        status, step, error = (
            "error",
            "Deployment failed",
            f"Railway reported the deployment {deployment_status.lower()}.",
        )
    elif deployment_status in {"WAITING", "NEEDS_APPROVAL"}:
        status, step, error = "deploying", "Needs approval in Railway", ""
    else:
        status, step, error = "deploying", f"Railway: {deployment_status.lower()}" if deployment_status else "Railway is building Möbius", ""

    public_url = f"https://{domain['domain']}"
    update_instance(
        conn,
        instance["id"],
        railway_domain=domain["domain"],
        public_url=public_url,
        recovery_url=f"{public_url}/recover",
        status=status,
        current_step=step,
        last_error=error,
        provision_token="",
        last_deployment_id=deployment.get("id") or instance["last_deployment_id"] or "",
    )
    add_instance_event(conn, instance["id"], "info", "Recovered public link from Railway")
    conn.commit()
    return conn.execute(
        "select * from mobius_instances where id = ?", (instance["id"],)
    ).fetchone()


METRIC_MEASUREMENTS = [
    "CPU_USAGE",
    "CPU_LIMIT",
    "MEMORY_USAGE_GB",
    "MEMORY_LIMIT_GB",
    "DISK_USAGE_GB",
    "NETWORK_RX_GB",
    "NETWORK_TX_GB",
]
RAILWAY_MONTHLY_RESOURCE_MINUTES = 30 * 24 * 60
RAILWAY_TRIAL_ALLOWANCE_USD = 5.0
RAILWAY_USAGE_RATES = {
    "CPU_USAGE": 20.0 / RAILWAY_MONTHLY_RESOURCE_MINUTES,
    "MEMORY_USAGE_GB": 10.0 / RAILWAY_MONTHLY_RESOURCE_MINUTES,
    "DISK_USAGE_GB": 0.15 / RAILWAY_MONTHLY_RESOURCE_MINUTES,
    "NETWORK_TX_GB": 0.05,
}


def latest_metric_value(metrics, measurement):
    for metric in metrics or []:
        if metric.get("measurement") != measurement:
            continue
        for value in reversed(metric.get("values") or []):
            if value.get("value") is not None:
                try:
                    return float(value["value"])
                except (TypeError, ValueError):
                    return None
    return None


def usage_value(usage, measurement):
    for item in usage or []:
        if item.get("measurement") != measurement:
            continue
        try:
            return float(item.get("value"))
        except (TypeError, ValueError):
            return None
    return None


def metric_values(metrics, measurement):
    for metric in metrics or []:
        if metric.get("measurement") == measurement:
            return [
                float(item["value"])
                for item in metric.get("values") or []
                if item.get("value") is not None
            ]
    return []


def numeric_percent(value, limit):
    try:
        value = float(value)
        limit = float(limit)
    except (TypeError, ValueError):
        return None
    if limit <= 0:
        return None
    return max(0.0, min(100.0, (value / limit) * 100))


def spark_percentages(metrics, measurement, limit=None):
    values = metric_values(metrics, measurement)[-18:]
    if not values:
        return []
    if limit:
        return [round(numeric_percent(value, limit) or 0, 2) for value in values]
    max_value = max(values)
    if max_value <= 0:
        return [0 for _ in values]
    return [round(max(0.0, min(100.0, (value / max_value) * 100)), 2) for value in values]


def format_usd(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if value <= 0:
        return "$0"
    if value < 0.01:
        return "<$0.01"
    return f"${value:.2f}"


def usage_cost(usage, value_key="value"):
    total = 0.0
    for measurement, rate in RAILWAY_USAGE_RATES.items():
        try:
            raw = next(
                float(item.get(value_key))
                for item in usage or []
                if item.get("measurement") == measurement
                and item.get(value_key) is not None
            )
        except (StopIteration, TypeError, ValueError):
            raw = 0.0
        total += raw * rate
    return total


def railway_metrics_snapshot(access_token, connection, instance):
    end = datetime.now(timezone.utc)
    start = end.replace(microsecond=0)
    start = datetime.fromtimestamp(start.timestamp() - 60 * 60, timezone.utc)
    data = railway_graphql(
        """
        query liveMetrics(
          $projectId: String!
          $serviceId: String!
          $environmentId: String!
          $startDate: DateTime!
          $endDate: DateTime!
          $measurements: [MetricMeasurement!]!
        ) {
          serviceInstance(serviceId: $serviceId, environmentId: $environmentId) {
            id
            region
            latestDeployment { id status updatedAt }
            domains {
              serviceDomains { id domain }
              customDomains { id domain }
            }
          }
          project(id: $projectId) {
            id
            name
            volumes {
              edges {
                node {
                  id
                  name
                  volumeInstances {
                    edges {
                      node {
                        id
                        externalId
                        serviceId
                        environmentId
                        mountPath
                        state
                        sizeMB
                        currentSizeMB
                      }
                    }
                  }
                }
              }
            }
          }
          metrics(
            projectId: $projectId
            serviceId: $serviceId
            environmentId: $environmentId
            startDate: $startDate
            endDate: $endDate
            measurements: $measurements
            sampleRateSeconds: 300
            averagingWindowSeconds: 300
          ) {
            measurement
            values { ts value }
          }
        }
        """,
        access_token,
        {
            "projectId": instance["railway_project_id"],
            "serviceId": instance["railway_service_id"],
            "environmentId": instance["railway_environment_id"],
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "measurements": METRIC_MEASUREMENTS,
        },
    )
    usage = []
    try:
        usage_data = railway_graphql(
            """
            query usage(
              $workspaceId: String!
              $projectId: String!
              $measurements: [MetricMeasurement!]!
            ) {
              usage(
                workspaceId: $workspaceId
                projectId: $projectId
                measurements: $measurements
              ) {
                measurement
                value
                tags { projectId serviceId environmentId volumeId volumeInstanceId }
              }
            }
            """,
            access_token,
            {
                "workspaceId": connection["railway_workspace_id"],
                "projectId": instance["railway_project_id"],
                "measurements": [
                    "CPU_USAGE",
                    "MEMORY_USAGE_GB",
                    "DISK_USAGE_GB",
                    "NETWORK_TX_GB",
                ],
            },
        )
        usage = usage_data.get("usage") or []
    except RailwayAPIError:
        usage = []

    project = data.get("project") or {}
    volumes = [edge.get("node") or {} for edge in ((project.get("volumes") or {}).get("edges") or [])]
    volume = volumes[0] if volumes else {}
    volume_instance = {}
    for candidate in volumes:
        volume_instance = matching_volume_instance(
            candidate, instance["railway_service_id"], instance["railway_environment_id"]
        )
        if volume_instance:
            volume = candidate
            break

    metrics = data.get("metrics") or []
    cpu_now = latest_metric_value(metrics, "CPU_USAGE")
    cpu_limit = latest_metric_value(metrics, "CPU_LIMIT")
    memory_now = latest_metric_value(metrics, "MEMORY_USAGE_GB")
    memory_limit = latest_metric_value(metrics, "MEMORY_LIMIT_GB")
    disk_now = latest_metric_value(metrics, "DISK_USAGE_GB")
    network_rx = latest_metric_value(metrics, "NETWORK_RX_GB")
    network_tx = latest_metric_value(metrics, "NETWORK_TX_GB")
    allocated_gb = volume_instance_size_gb(volume_instance) or coerce_volume_size_gb(instance["volume_size_gb"])
    try:
        volume_current_gb = float((volume_instance or {}).get("currentSizeMB") or 0) / 1024
    except (TypeError, ValueError):
        volume_current_gb = 0
    disk_used_gb = disk_now if disk_now is not None else volume_current_gb
    deployment = (data.get("serviceInstance") or {}).get("latestDeployment") or {}
    deployment_status = (deployment.get("status") or instance["status"] or "").lower()
    used_cost = usage_cost(usage)
    network_spark = spark_percentages(metrics, "NETWORK_TX_GB")

    return {
        "updated_at": now_iso(),
        "deployment_status": deployment_status,
        "service_instance_id": (data.get("serviceInstance") or {}).get("id") or "",
        "railway_project_name": project.get("name") or instance["railway_project_name"] or "",
        "cpu": {
            "value": cpu_now,
            "limit": cpu_limit,
            "label": format_cpu_label(cpu_now),
            "limit_label": format_cpu_label(cpu_limit),
            "percent": percent_label(cpu_now, cpu_limit),
            "spark": spark_percentages(metrics, "CPU_USAGE", cpu_limit),
        },
        "memory": {
            "value_gb": memory_now,
            "limit_gb": memory_limit,
            "label": format_gb_label(memory_now),
            "limit_label": format_gb_label(memory_limit),
            "percent": percent_label(memory_now, memory_limit),
            "spark": spark_percentages(metrics, "MEMORY_USAGE_GB", memory_limit),
        },
        "volume": {
            "id": (volume or {}).get("id") or instance["railway_volume_id"] or "",
            "state": (volume_instance or {}).get("state") or "",
            "used_gb": disk_used_gb,
            "allocated_gb": allocated_gb,
            "used_label": format_gb_label(disk_used_gb),
            "allocated_label": format_gb_label(allocated_gb),
            "percent": percent_label(disk_used_gb, allocated_gb),
            "spark": spark_percentages(metrics, "DISK_USAGE_GB", allocated_gb),
        },
        "network": {
            "rx_gb": network_rx,
            "tx_gb": network_tx,
            "rx_label": format_gb_label(network_rx),
            "tx_label": format_gb_label(network_tx),
            "percent": f"{network_spark[-1]}%" if network_spark else "0%",
            "spark": network_spark,
        },
        "usage_24h": {
            "cpu_label": format_cpu_label(usage_value(usage, "CPU_USAGE")),
            "memory_label": format_gb_label(usage_value(usage, "MEMORY_USAGE_GB")),
            "disk_label": format_gb_label(usage_value(usage, "DISK_USAGE_GB")),
            "rx_label": format_gb_label(usage_value(usage, "NETWORK_RX_GB")),
            "tx_label": format_gb_label(usage_value(usage, "NETWORK_TX_GB")),
        },
        "cost": {
            "available": bool(usage),
            "used": used_cost,
            "allowance": RAILWAY_TRIAL_ALLOWANCE_USD,
            "label": format_usd(used_cost),
            "used_label": format_usd(used_cost),
            "allowance_label": format_usd(RAILWAY_TRIAL_ALLOWANCE_USD),
            "percent": percent_label(used_cost, RAILWAY_TRIAL_ALLOWANCE_USD, decimals=1),
            "note": "Current project usage to date. Billed by Railway.",
        },
    }


def provision_instance(instance_id, token):
    with closing(connect_db()) as conn:
        project_id = None
        access_token = None

        def cancel_requested():
            row = conn.execute(
                "select status, provision_token from mobius_instances where id = ?",
                (instance_id,),
            ).fetchone()
            return row is None or row["status"] == "deleted" or row["provision_token"] != token

        def cleanup_if_cancelled():
            row = conn.execute(
                "select status, provision_token from mobius_instances where id = ?",
                (instance_id,),
            ).fetchone()
            if row and row["status"] == "deleted" and project_id and access_token:
                try:
                    delete_project(access_token, project_id)
                except RailwayAPIError:
                    pass
                add_instance_event(conn, instance_id, "info", "Deleted during provisioning; Railway project torn down")
                conn.commit()
            return row is None or (row and (row["status"] == "deleted" or row["provision_token"] != token))

        try:
            instance = provisioning_row(conn, instance_id, token)
            if instance is None:
                return
            connection = conn.execute(
                "select * from railway_connections where id = ?",
                (instance["railway_connection_id"],),
            ).fetchone()
            if connection is None:
                raise RailwayAPIError("Railway is not connected.")

            update_instance(conn, instance_id, status="creating", current_step="Loading Railway token", last_error=None)
            access_token = refresh_railway_access_token(connection, conn)

            project_id = instance["railway_project_id"] or None
            if not project_id:
                update_instance(conn, instance_id, current_step="Loading Railway template")
                add_instance_event(conn, instance_id, "info", f"Loading Railway template {RAILWAY_TEMPLATE_CODE}")
                template = fetch_template(RAILWAY_TEMPLATE_CODE)
                if cleanup_if_cancelled():
                    return

                # One call creates the project, service, /data volume, and starts
                # the build (see deploy_template). We then wait for resources to
                # register and hand off build-progress tracking to the status poll.
                update_instance(conn, instance_id, current_step="Creating your Railway project")
                payload = deploy_template(
                    access_token,
                    template,
                    connection["railway_workspace_id"],
                    volume_size_gb=instance["volume_size_gb"],
                )
                project_id = payload["projectId"]
                if cleanup_if_cancelled():
                    return
                update_instance(
                    conn,
                    instance_id,
                    railway_project_id=project_id,
                    railway_project_name=instance["display_name"],
                    railway_workspace_name=connection["railway_workspace_name"],
                    last_deployment_id=payload.get("workflowId") or "",
                    current_step="Building Möbius (this can take a few minutes)",
                )
                add_instance_event(conn, instance_id, "info", "Railway project created; template deploying")
            else:
                update_instance(
                    conn,
                    instance_id,
                    current_step="Resuming interrupted Railway deployment",
                )
                add_instance_event(conn, instance_id, "info", "Resuming interrupted Railway deployment")
            if cleanup_if_cancelled():
                return

            def _tick(elapsed):
                if not cancel_requested():
                    update_instance(conn, instance_id, current_step=f"Building Möbius ({elapsed}s)")

            _project, service, volume = wait_for_template_service(
                access_token, project_id, on_wait=_tick
            )
            if cleanup_if_cancelled():
                return
            service_id = service["id"]
            environment_id = project_environment_id(access_token, project_id)
            volume_instance = matching_volume_instance(volume, service_id, environment_id)
            actual_volume_gb = volume_instance_size_gb(volume_instance)
            update_instance(
                conn,
                instance_id,
                railway_service_id=service_id,
                railway_volume_id=volume.get("id") or "",
                railway_environment_id=environment_id,
                volume_size_gb=format_volume_gb(actual_volume_gb) if actual_volume_gb else instance["volume_size_gb"],
                current_step="Creating your public link",
            )
            inst_now = provisioning_row(conn, instance_id, token)
            if inst_now is None:
                cleanup_if_cancelled()
                return
            if inst_now and (inst_now["cpu"] or inst_now["memory_mb"]):
                try:
                    set_service_limits(
                        access_token,
                        environment_id,
                        service_id,
                        inst_now["cpu"] or None,
                        inst_now["memory_mb"] or None,
                    )
                    add_instance_event(
                        conn,
                        instance_id,
                        "info",
                        f"Resource caps set: {inst_now['cpu'] or '-'} vCPU / {memory_mb_label(inst_now['memory_mb']) or '-'} RAM",
                    )
                except RailwayAPIError as exc:
                    add_instance_event(
                        conn,
                        instance_id,
                        "info",
                        f"Could not set resource caps (Möbius still deploys): {compact_api_error(exc)}",
                    )
            add_instance_event(
                conn,
                instance_id,
                "info",
                f"Möbius service created with a {volume_size_label(actual_volume_gb or instance['volume_size_gb'])} /data volume",
            )

            if cleanup_if_cancelled():
                return

            def _domain_tick(elapsed):
                if not cancel_requested():
                    update_instance(
                        conn,
                        instance_id,
                        current_step=f"Waiting for Railway service instance ({elapsed}s)",
                    )

            domain = create_service_domain_with_retry(
                access_token, service_id, environment_id, on_wait=_domain_tick
            )
            if cleanup_if_cancelled():
                return
            public_url = f"https://{domain['domain']}"
            deployment = latest_deployment(access_token, project_id, service_id, environment_id)
            deployment_status = (deployment.get("status") or "").upper()
            app_ready = deployment_status in DEPLOY_STATUS_OK and mobius_app_healthy(public_url)
            final_status = "ready" if app_ready else "deploying"
            final_step = "Ready" if app_ready else (
                "Recovery online; Möbius is still starting"
                if deployment_status in DEPLOY_STATUS_OK
                else "Railway is building Möbius"
            )
            update_instance(
                conn,
                instance_id,
                railway_domain=domain["domain"],
                public_url=public_url,
                recovery_url=f"{public_url}/recover",
                status=final_status,
                current_step=final_step,
                provision_token="",
                last_deployment_id=deployment.get("id") or instance["last_deployment_id"] or "",
            )
            add_instance_event(conn, instance_id, "info", f"Public link created; {final_step.lower()}")
            conn.commit()
        except Exception as exc:
            if provisioning_row(conn, instance_id, token) is None:
                cleanup_if_cancelled()
                return
            message = compact_api_error(exc)
            update_instance(
                conn,
                instance_id,
                status="error",
                current_step="Deployment failed",
                last_error=message,
                provision_token="",
            )
            add_instance_event(conn, instance_id, "error", message)
            if project_id:
                # We do NOT auto-delete: the build may be fine and only a late
                # step (e.g. domain) failed. Surface it so the user can review or
                # Delete the project rather than being silently billed.
                add_instance_event(
                    conn,
                    instance_id,
                    "info",
                    "A Railway project was created before the error. Use Delete to remove it, or review it on Railway.",
                )
            conn.commit()


def reconcile_deployment_status(conn, instance):
    # On demand (called from the status poll): while an instance is "deploying",
    # ask Railway for the latest deployment status and advance it to ready/error.
    # Throttled via last_seen_at so page polling can't hammer the Railway API.
    if can_recover_public_link(instance):
        try:
            return recover_public_link(conn, instance)
        except RailwayAPIError as exc:
            update_instance(
                conn,
                instance["id"],
                current_step="Waiting for Railway service instance",
                last_seen_at=now_iso(),
                last_error=compact_api_error(exc),
            )
            return conn.execute(
                "select * from mobius_instances where id = ?", (instance["id"],)
            ).fetchone()

    if instance["status"] != "deploying":
        return instance
    if not (
        instance["railway_project_id"]
        and instance["railway_service_id"]
        and instance["railway_environment_id"]
    ):
        return instance
    if instance["last_seen_at"]:
        try:
            age = time.time() - datetime.fromisoformat(instance["last_seen_at"]).timestamp()
            if age < 8:
                return instance
        except ValueError:
            pass
    connection = conn.execute(
        "select * from railway_connections where id = ?",
        (instance["railway_connection_id"],),
    ).fetchone()
    if connection is None:
        return instance

    fields = {"last_seen_at": now_iso()}
    try:
        access_token = refresh_railway_access_token(connection, conn)
        node = latest_deployment(
            access_token,
            instance["railway_project_id"],
            instance["railway_service_id"],
            instance["railway_environment_id"],
        )
        status = (node.get("status") or "").upper()
        if status in DEPLOY_STATUS_OK:
            if mobius_app_healthy(instance["public_url"]):
                fields.update(status="ready", current_step="Ready")
                add_instance_event(conn, instance["id"], "info", "Möbius is live")
            else:
                fields.update(current_step="Recovery online; Möbius is still starting")
        elif status in DEPLOY_STATUS_BAD:
            fields.update(
                status="error",
                current_step="Deployment failed",
                last_error=f"Railway reported the deployment {status.lower()}.",
            )
            add_instance_event(conn, instance["id"], "error", f"Deployment {status.lower()}")
        elif status in {"WAITING", "NEEDS_APPROVAL"}:
            fields.update(current_step="Needs approval in Railway")
        elif status:
            fields.update(current_step=f"Railway: {status.lower()}")
    except RailwayAPIError:
        pass  # transient; try again on the next poll

    update_instance(conn, instance["id"], **fields)
    return conn.execute(
        "select * from mobius_instances where id = ?", (instance["id"],)
    ).fetchone()


def start_provisioning(instance_id, include_creating=False):
    token = claim_provisioning(instance_id, include_creating=include_creating)
    if not token:
        return False
    thread = threading.Thread(target=provision_instance, args=(instance_id, token), daemon=True)
    thread.start()
    return True


def recover_interrupted_provisioning():
    with closing(connect_db()) as conn:
        rows = conn.execute(
            """
            select id, status, updated_at
            from mobius_instances
            where status in ('queued', 'creating')
            """,
        ).fetchall()
    for row in rows:
        include_creating = row["status"] == "creating"
        if row["status"] == "queued" or timestamp_age_seconds(row["updated_at"]) > PROVISIONING_STALE_SECONDS:
            start_provisioning(row["id"], include_creating=include_creating)


recover_interrupted_provisioning()


LAYOUT = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Launch a private Möbius AI workspace in a Railway account you control.">
  <link rel="canonical" href="{{ canonical_url }}">
  <meta name="theme-color" content="#0d0d0d">
  <title>Möbius: Your private AI workspace</title>
  <link rel="icon" type="image/png" href="{{ favicon_url }}">
  <link rel="apple-touch-icon" href="{{ favicon_url }}">
  <link rel="preconnect" href="https://rsms.me/">
  <link rel="stylesheet" href="https://rsms.me/inter/inter.css">
  <style>
    :root {
      color-scheme: dark;
      --bg: #0d0d0d;
      --surface: #171717;
      --surface2: #212121;
      --surface3: #111111;
      --border: #2a2a2a;
      --border-light: #1f1f1f;
      --text: #ececec;
      --muted: #a8a8a8;
      --accent: #8b6cf7;
      --accent-hover: #7c5ce6;
      --accent-active: #6d4bd7;
      --accent-dim: rgba(139, 108, 247, 0.14);
      --ok: #10b981;
      --ok-soft: rgba(16, 185, 129, 0.14);
      --warn: #f0c674;
      --warn-soft: rgba(240, 198, 116, 0.13);
      --danger: #f87171;
      --danger-soft: rgba(248, 113, 113, 0.13);
      --radius: 8px;
      --spring: cubic-bezier(0.16, 1, 0.3, 1);
    }

    * { box-sizing: border-box; }
    html { color-scheme: dark; }
    html, body { margin: 0; min-height: 100%; }
    body {
      background:
        linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0) 220px),
        var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
      line-height: 1.55;
      -webkit-font-smoothing: antialiased;
      font-feature-settings: "cv01", "ss01";
      overflow-x: hidden;
      -webkit-tap-highlight-color: transparent;
    }
    a { color: inherit; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .shell { max-width: 1120px; margin: 0 auto; padding: 20px 20px 64px; }
    .narrow { max-width: 460px; padding-top: 72px; }
    .login-shell {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr auto;
      gap: clamp(34px, 6vh, 72px);
      position: relative;
      isolation: isolate;
    }
    .login-shell::before {
      content: "";
      position: fixed;
      z-index: -1;
      width: min(62vw, 760px);
      aspect-ratio: 1;
      left: -18vw;
      top: 16vh;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(139, 108, 247, 0.15), rgba(139, 108, 247, 0) 68%);
      pointer-events: none;
    }
    .login-topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
    }
    .login-topbar .mark { width: 40px; height: 40px; }
    .login-topbar .subtitle { font-size: 12px; }
    .login-nav { display: flex; align-items: center; gap: 18px; color: var(--muted); font-size: 13px; }
    .login-nav a:hover { color: var(--text); text-decoration: none; }
    .login-layout {
      display: grid;
      grid-template-columns: minmax(0, 0.95fr) minmax(380px, 0.72fr);
      align-items: center;
      gap: clamp(44px, 7vw, 88px);
      width: 100%;
    }
    .login-story { max-width: 630px; }
    .login-kicker {
      display: inline-flex;
      align-items: center;
      gap: 9px;
      margin: 0 0 18px;
      color: #b9a7ff;
      font-size: 13px;
      font-weight: 700;
    }
    .login-kicker::before {
      content: "";
      width: 22px;
      height: 2px;
      border-radius: 999px;
      background: var(--accent);
    }
    .login-story h2 {
      max-width: 12ch;
      font-size: clamp(42px, 5.4vw, 66px);
      font-weight: 730;
      line-height: 0.98;
      letter-spacing: -0.035em;
      text-wrap: balance;
    }
    .login-lead {
      max-width: 60ch;
      margin: 24px 0 0;
      color: var(--muted);
      font-size: clamp(16px, 1.8vw, 19px);
      line-height: 1.55;
      text-wrap: pretty;
    }
    .login-facts {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 20px;
      margin: 26px 0 0;
      padding: 13px 0;
      border-block: 1px solid var(--border-light);
    }
    .login-facts span { color: #c9c9c9; font-size: 12px; font-weight: 650; }
    .login-facts span::before { content: ""; display: inline-block; width: 6px; height: 6px; margin: 0 8px 1px 0; border-radius: 50%; background: var(--accent); }
    .login-facts span:nth-child(2)::before { background: #7dd3fc; }
    .login-facts span:nth-child(3)::before { background: var(--ok); }
    .login-product-preview {
      margin: 24px 0 0;
      overflow: hidden;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: #090909;
    }
    .login-product-preview img {
      display: block;
      width: 100%;
      height: auto;
      aspect-ratio: 16 / 7.5;
      object-fit: cover;
      object-position: top;
    }
    .login-product-preview figcaption {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 14px;
      padding: 10px 12px;
      border-top: 1px solid var(--border-light);
      color: var(--muted);
      font-size: 11px;
    }
    .login-product-preview strong { color: var(--text); font-size: 11px; }
    .login-card {
      width: 100%;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      overflow: hidden;
      box-shadow: 0 8px 8px rgba(0, 0, 0, 0.24);
    }
    .login-card-main { padding: clamp(24px, 4vw, 34px); }
    .login-card-label {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0 0 16px;
      color: #c7bcff;
      font-size: 12px;
      font-weight: 700;
    }
    .login-card-label::before {
      content: "";
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--accent);
      box-shadow: 0 0 0 4px var(--accent-dim);
    }
    .login-card h2 { font-size: 25px; line-height: 1.08; }
    .login-card-copy { margin: 10px 0 24px; color: var(--muted); font-size: 14px; text-wrap: pretty; }
    .login-card .provider-list { margin: 0; }
    .login-card .provider-list form, .login-card .provider-list button { width: 100%; }
    .login-card .provider-list button, .login-card-main > form .primary { min-height: 50px; font-size: 14px; }
    .login-after {
      display: grid;
      gap: 10px;
      padding: 16px clamp(24px, 4vw, 34px);
      border-top: 1px solid var(--border-light);
      background: var(--surface3);
    }
    .login-after strong { font-size: 12px; color: var(--text); }
    .login-after span { color: var(--muted); font-size: 12px; line-height: 1.45; }
    .login-after ol {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
      counter-reset: launch-step;
    }
    .login-after li {
      counter-increment: launch-step;
      display: grid;
      gap: 3px;
      min-width: 0;
      color: var(--muted);
      font-size: 10px;
      line-height: 1.35;
    }
    .login-after li::before {
      content: "0" counter(launch-step);
      color: #a992ff;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 9px;
      font-weight: 700;
    }
    .login-trust {
      display: flex;
      align-items: flex-start;
      gap: 9px;
      margin: 18px 0 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }
    .login-trust::before {
      content: "";
      width: 7px;
      height: 7px;
      margin-top: 5px;
      border-radius: 50%;
      background: var(--ok);
      flex: none;
    }
    .login-requirement {
      margin: 16px 0 0;
      padding-top: 14px;
      border-top: 1px solid var(--border-light);
      color: var(--muted);
      font-size: 11px;
      line-height: 1.5;
    }
    .login-requirement strong { color: var(--text); }
    .login-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      color: var(--muted);
      font-size: 12px;
    }
    .login-footer-links { display: flex; flex-wrap: wrap; gap: 16px; }
    .login-footer a:hover { color: var(--text); text-decoration: none; }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }
    .brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
    .brand.block { align-items: flex-start; margin-bottom: 18px; }
    .mark {
      width: 48px;
      height: 48px;
      border-radius: 0;
      object-fit: contain;
      display: block;
      flex: none;
      filter: drop-shadow(0 6px 18px rgba(139, 108, 247, 0.22));
    }
    h1, h2, h3 { margin: 0; line-height: 1.2; letter-spacing: 0; }
    h1 { font-size: 20px; font-weight: 700; }
    h2 { font-size: 19px; font-weight: 700; }
    h3 { font-size: 15px; font-weight: 650; }
    .subtitle, .hint, .muted { color: var(--muted); }
    .subtitle { margin: 3px 0 0; font-size: 13px; overflow-wrap: anywhere; }
    .hint { margin: 6px 0 0; font-size: 13px; }
    .fine { margin: 8px 0 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
    .stack { display: grid; gap: 14px; }
    .panel {
      background:
        linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0) 120px),
        var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow: hidden;
      box-shadow: 0 12px 40px rgba(0,0,0,0.22);
    }
    .section { padding: 20px; }
    .section + .section { border-top: 1px solid var(--border); }
    .section-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }
    .hero-panel {
      display: grid;
      gap: 20px;
      padding: 28px;
    }
    .hero-copy { max-width: 660px; }
    .hero-copy h2 { font-size: clamp(28px, 5vw, 52px); line-height: 1.02; font-weight: 720; }
    .kicker {
      margin: 0 0 10px;
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0;
    }
    .connect-center {
      display: grid;
      gap: 12px;
      place-items: center;
      padding: 22px;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: color-mix(in srgb, var(--surface2) 72%, transparent);
    }
    .connect-center form { width: min(100%, 320px); }
    .connect-center .button, .connect-center button { width: 100%; }
    .trust-strip, .billing-strip, .metric-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    .trust-item, .billing-item, .metric-card {
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: var(--bg);
      padding: 12px;
      min-width: 0;
    }
    .trust-item strong, .billing-item strong, .metric-card strong {
      display: block;
      color: var(--text);
      font-size: 13px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }
    .trust-item span, .billing-item span, .metric-card span, .metric-card small {
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }
    .billing-strip {
      margin-top: 14px;
    }
    .deploy-card {
      display: grid;
      gap: 8px;
      width: min(100%, 560px);
      margin: 0 auto;
    }
    .actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
    .actions.left { justify-content: flex-start; }
    .button, button {
      appearance: none;
      min-height: 40px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--surface2);
      color: var(--text);
      padding: 9px 13px;
      font: inherit;
      font-size: 13px;
      font-weight: 650;
      text-decoration: none;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      white-space: nowrap;
      transition: transform 120ms var(--spring), background 180ms ease, border-color 180ms ease, color 180ms ease, box-shadow 180ms ease;
      touch-action: manipulation;
    }
    .button.subtle, button.subtle { background: transparent; color: var(--muted); }
    .button.primary, button.primary {
      background: var(--accent-hover);
      border-color: var(--accent-hover);
      color: #ffffff;
      box-shadow: 0 4px 8px rgba(139, 108, 247, 0.22);
    }
    .button.danger, button.danger {
      color: var(--danger);
      border-color: rgba(248, 113, 113, 0.28);
      background: var(--danger-soft);
    }
    .button.danger:hover, button.danger:hover {
      color: #fecaca;
      border-color: rgba(248, 113, 113, 0.48);
      background: rgba(248, 113, 113, 0.18);
    }
    .button.icon, button.icon {
      width: 40px;
      min-width: 40px;
      padding: 0;
      font-size: 16px;
    }
    .button.large, button.large {
      min-height: 52px;
      font-size: 15px;
      border-radius: 12px;
    }
    button:disabled { cursor: not-allowed; opacity: 0.55; }
    .button:hover, button:hover { border-color: var(--accent); text-decoration: none; }
    .button.primary:hover, button.primary:hover { background: var(--accent-active); }
    .button:active, button:active { transform: scale(0.97); }
    .button.copied, button.copied {
      color: var(--ok);
      border-color: rgba(16, 185, 129, 0.32);
      background: var(--ok-soft);
    }
    .open-app {
      min-width: 92px;
      gap: 7px;
    }
    .recovery-link {
      min-width: 112px;
      color: color-mix(in srgb, var(--accent) 82%, white 12%);
      border-color: rgba(139, 108, 247, 0.32);
      background: rgba(139, 108, 247, 0.12);
    }
    .recovery-link:hover {
      color: #fff;
      background: rgba(139, 108, 247, 0.18);
    }
    .railway-link {
      min-width: 82px;
    }
    .topbar .button, .topbar button {
      min-height: 36px;
      padding: 7px 11px;
    }
    .icon-svg {
      width: 16px;
      height: 16px;
      display: block;
      fill: none;
      stroke: currentColor;
      stroke-width: 2;
      stroke-linecap: round;
      stroke-linejoin: round;
      flex: none;
    }
    .workspace-pill {
      min-height: 36px;
      display: inline-flex;
      align-items: center;
      padding: 6px 12px;
      font-size: 13px;
      border-color: rgba(16, 185, 129, 0.28);
      background: rgba(16, 185, 129, 0.12);
    }
    .button:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible, summary:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }
    form { display: grid; gap: 12px; margin: 0; }
    label { display: grid; gap: 6px; color: var(--muted); font-size: 12px; font-weight: 620; }
    input, select {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 8px;
      min-height: 40px;
      padding: 9px 10px;
      font: inherit;
      font-size: 16px;
      color: var(--text);
      background: var(--bg);
    }
    .form-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .tier-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    .tier-option { position: relative; }
    .tier-option input {
      position: absolute;
      opacity: 0;
      pointer-events: none;
    }
    .tier-card {
      display: grid;
      gap: 5px;
      height: 100%;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      cursor: pointer;
      background: var(--bg);
      color: var(--muted);
      font-size: 12px;
      font-weight: 620;
    }
    .tier-title {
      color: var(--text);
      font-size: 13px;
      font-weight: 720;
    }
    .tier-blurb, .tier-spec { color: var(--muted); }
    .tier-option input:checked + .tier-card {
      border-color: var(--accent);
      background: var(--surface2);
    }
    .tier-option input:focus-visible + .tier-card {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }
    .full { grid-column: 1 / -1; }
    .deploy-submit {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }
    details { color: var(--muted); font-size: 13px; }
    summary { cursor: pointer; width: fit-content; }
    details[open] summary { margin-bottom: 10px; }
    .instance-list { display: grid; gap: 12px; }
    .instance {
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--bg);
      padding: 15px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      position: relative;
      overflow: hidden;
      animation: enter 260ms var(--spring);
    }
    .instance details { grid-column: 1 / -1; margin-top: 2px; }
    .instance-main { min-width: 0; }
    .url {
      display: inline-block;
      margin-top: 5px;
      color: var(--accent);
      font-size: 13px;
      word-break: break-word;
    }
    .ready-note {
      margin-top: 10px;
      border-left: 2px solid var(--ok);
      padding-left: 10px;
    }
    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin-top: 11px;
      color: var(--muted);
      font-size: 12px;
    }
    .pill {
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 3px 8px;
      background: var(--surface2);
      color: var(--muted);
      white-space: nowrap;
    }
    .pill.ok { color: var(--ok); background: var(--ok-soft); border-color: rgba(99, 217, 140, 0.25); }
    .pill.warn { color: var(--warn); background: var(--warn-soft); border-color: rgba(242, 195, 107, 0.28); }
    .pill.err { color: var(--danger); background: var(--danger-soft); border-color: rgba(248, 113, 113, 0.28); }
    .instance-actions { display: flex; gap: 8px; align-items: flex-start; justify-content: flex-end; flex-wrap: wrap; min-width: 108px; align-self: start; }
    .metric-grid {
      grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
      grid-column: 1 / -1;
      margin-top: 2px;
    }
    .metric-card {
      background: var(--surface3);
      padding: 11px;
    }
    .metric-card strong {
      font-size: 17px;
      font-variant-numeric: tabular-nums;
    }
    .meter {
      height: 4px;
      margin-top: 9px;
      background: var(--surface2);
      border-radius: 999px;
      overflow: hidden;
    }
    .meter > span {
      display: block;
      height: 100%;
      width: 0%;
      margin: 0;
      background: var(--accent);
      transition: width 280ms ease;
    }
    .progress-line {
      grid-column: 1 / -1;
      height: 3px;
      border-radius: 999px;
      overflow: hidden;
      background: var(--surface2);
    }
    .progress-line span {
      display: block;
      height: 100%;
      width: 42%;
      background: linear-gradient(90deg, transparent, var(--accent), transparent);
      animation: sweep 1.4s ease-in-out infinite;
    }
    .command {
      border-radius: 8px;
      border: 1px solid var(--border);
      background: #0a0a0a;
      color: #e8e3ff;
      min-height: 38px;
      padding: 9px 10px;
      font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      overflow-x: auto;
      white-space: nowrap;
    }
    .notice {
      border: 1px solid rgba(242, 195, 107, 0.28);
      background: var(--warn-soft);
      color: #f5d79a;
      border-radius: 8px;
      padding: 12px 13px;
      font-size: 13px;
    }
    .notice + form { margin-top: 12px; }
    .notice.danger {
      border-color: rgba(248, 113, 113, 0.28);
      background: var(--danger-soft);
      color: #fecaca;
    }
    .empty {
      border: 1px dashed var(--border);
      border-radius: 8px;
      padding: 22px;
      color: var(--muted);
      background: var(--bg);
      font-size: 13px;
    }
    .login-copy { margin: 0 0 18px; color: var(--muted); font-size: 14px; }
    .provider-list { display: grid; gap: 10px; margin-bottom: 16px; }
    .divider { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 12px; margin: 6px 0 2px; }
    .divider::before, .divider::after { content: ""; height: 1px; background: var(--border); flex: 1; }
    .footer-links {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      margin-top: 14px;
      color: var(--muted);
      font-size: 12px;
    }
    .inline-link {
      color: var(--muted);
      font-size: 13px;
    }
    .inline-link:hover { color: var(--text); }
    .advanced {
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--bg);
      padding: 12px;
    }
    .advanced summary {
      color: var(--text);
      font-weight: 650;
    }
    .advanced .form-grid, .advanced .trust-grid { margin-top: 12px; }
    .trust-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .trust-card {
      border: 1px solid var(--border);
      border-radius: 8px;
      background: transparent;
      padding: 14px;
    }
    .trust-card ul {
      margin: 10px 0 0;
      padding-left: 18px;
      color: var(--muted);
      font-size: 13px;
    }
    .trust-card li + li { margin-top: 6px; }
    .launch-surface {
      display: grid;
      gap: 18px;
      padding: 18px;
    }
    .launch-head {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: start;
    }
    .launch-title {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }
    .launch-title h2 { font-size: clamp(26px, 4vw, 42px); }
    .launch-mark {
      width: 64px;
      height: 64px;
      border-radius: 0;
      object-fit: contain;
      box-shadow: 0 12px 30px rgba(0,0,0,0.26);
    }
    .railway-connect {
      min-height: 58px;
      min-width: min(100%, 290px);
      flex-direction: column;
      gap: 1px;
    }
    .button-main { font-size: 15px; }
    .button-sub { font-size: 11px; font-weight: 600; opacity: 0.82; }
    .signal-strip {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    .signal {
      border: 1px solid var(--border);
      border-radius: 999px;
      background: color-mix(in srgb, var(--surface2) 78%, transparent);
      color: var(--muted);
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 650;
      white-space: nowrap;
    }
    .signal strong { color: var(--text); font-weight: 720; }
    /* Onboarding stepper: create Railway account -> connect -> deploy. Steps are
       guided, not gated: step 1 leads, opening it promotes step 2, but a user
       who already has a Railway account can Connect at any time. */
    .stepper { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
    .step {
      display: grid;
      grid-template-columns: 34px minmax(0, 1fr);
      gap: 14px;
      align-items: start;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: color-mix(in srgb, var(--surface2) 42%, transparent);
      padding: 16px;
      transition: border-color 180ms ease, background 180ms ease, opacity 180ms ease;
    }
    .step-num {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 34px;
      height: 34px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--muted);
      font-size: 14px;
      font-weight: 720;
      flex: none;
    }
    .step-body { min-width: 0; display: grid; gap: 4px; }
    .step-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .step-cta { margin-top: 10px; align-self: start; min-width: min(100%, 260px); }
    .step.locked { opacity: 0.6; }
    .step.locked .step-num { background: transparent; }
    .step-done-badge { display: none; font-size: 12px; color: var(--ok); font-weight: 650; }
    /* Step 2 reads as the secondary action until step 1 is opened. */
    .step-connect:not([disabled]) {
      background: var(--surface2);
      border-color: var(--border);
      color: var(--text);
      box-shadow: none;
    }
    /* Once the signup tab is opened, check off step 1 and promote step 2. */
    .stepper.step1-done .step[data-step="1"] { opacity: 0.72; }
    .stepper.step1-done .step[data-step="1"] .step-num {
      background: var(--ok-soft);
      border-color: transparent;
      color: var(--ok);
      font-size: 0;
    }
    .stepper.step1-done .step[data-step="1"] .step-num::after { content: "✓"; font-size: 16px; }
    .stepper.step1-done .step-done-badge { display: inline; }
    .stepper.step1-done .step-cta.step-create {
      background: var(--surface2);
      border-color: var(--border);
      color: var(--muted);
      box-shadow: none;
    }
    .stepper.step1-done .step-connect:not([disabled]) {
      background: var(--accent-hover);
      border-color: var(--accent-hover);
      color: #ffffff;
      box-shadow: 0 4px 8px rgba(139, 108, 247, 0.22);
    }
    .stepper.step1-done .step-connect:not([disabled]):hover { background: var(--accent-active); }
    .deploy-inline {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto;
      gap: 8px;
      align-items: end;
    }
    .deploy-composer {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto;
      gap: 6px;
      align-items: stretch;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--bg);
      padding: 6px;
      transition: border-color 180ms ease, background 180ms ease, box-shadow 180ms ease;
    }
    .deploy-composer:focus-within {
      border-color: color-mix(in srgb, var(--accent) 70%, white 0%);
      background: color-mix(in srgb, var(--surface2) 38%, var(--bg));
      box-shadow: 0 0 0 4px rgba(139, 108, 247, 0.1);
    }
    .deploy-name {
      display: grid;
      gap: 1px;
      padding: 2px 8px 3px;
      min-width: 0;
      color: var(--muted);
      font-size: 10px;
      font-weight: 700;
    }
    .deploy-name span {
      display: block;
    }
    .deploy-name input {
      border: 0;
      min-height: 30px;
      padding: 0;
      background: transparent;
      border-radius: 0;
      color: var(--text);
      font: inherit;
      font-size: 15px;
      font-weight: 700;
      min-width: 0;
    }
    .deploy-name input:focus-visible {
      outline: 0;
    }
    .deploy-button {
      min-width: 112px;
      min-height: 40px;
      box-shadow: none !important;
    }
    .control-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 10px;
    }
    .limit-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      padding: 10px;
    }
    .input-shell {
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: var(--bg);
      padding: 6px 9px 8px;
      transition: border-color 180ms ease, background 180ms ease, box-shadow 180ms ease;
    }
    .input-shell:focus-within {
      border-color: color-mix(in srgb, var(--accent) 70%, white 0%);
      background: color-mix(in srgb, var(--surface2) 64%, transparent);
      box-shadow: 0 0 0 4px rgba(139, 108, 247, 0.12);
    }
    .input-shell span {
      display: block;
      color: var(--muted);
      font-size: 10px;
      font-weight: 700;
      margin-bottom: 1px;
    }
    .input-shell input, .input-shell select {
      border: 0;
      min-height: 26px;
      padding: 0;
      background: transparent;
      border-radius: 0;
      font-size: 14px;
    }
    .input-shell input:focus-visible, .input-shell select:focus-visible { outline: 0; }
    .compact-details {
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: color-mix(in srgb, var(--surface2) 55%, transparent);
      padding: 0;
      overflow: hidden;
    }
    .compact-details summary {
      align-items: center;
      color: var(--text);
      display: flex;
      gap: 10px;
      justify-content: space-between;
      font-weight: 700;
      min-height: 38px;
      padding: 8px 10px;
      width: 100%;
    }
    .compact-details summary small {
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
      text-align: right;
    }
    .compact-details[open] summary {
      border-bottom: 1px solid var(--border);
      margin-bottom: 0;
    }
    .compact-details[open] summary small { color: var(--accent); }
    .compact-details .control-row {
      margin-top: 0 !important;
      padding: 12px;
    }
    .compact-details .limit-grid { margin-top: 0 !important; }
    .limits-note {
      border-top: 1px solid var(--border-light);
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
      margin: 0;
      padding: 0 10px 10px;
    }
    .create-panel {
      background: color-mix(in srgb, var(--surface) 72%, transparent);
      box-shadow: none;
    }
    .create-drawer {
      color: var(--muted);
      font-size: 13px;
    }
    .create-drawer summary {
      width: 100%;
      list-style: none;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 13px 15px;
      color: var(--text);
    }
    .create-drawer summary::-webkit-details-marker { display: none; }
    .create-drawer summary:hover { background: rgba(255,255,255,0.025); }
    .create-drawer summary strong {
      display: block;
      font-size: 15px;
      line-height: 1.25;
    }
    .create-drawer summary span span {
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 500;
    }
    .create-plus {
      width: 34px;
      height: 34px;
      border-radius: 999px;
      display: inline-grid;
      place-items: center;
      background: var(--surface2);
      color: var(--muted);
      flex: none;
      transition: transform 180ms var(--spring), background 180ms ease, color 180ms ease;
    }
    .create-drawer[open] .create-plus { transform: rotate(45deg); background: var(--accent-dim); color: var(--accent); }
    .create-drawer[open] summary {
      border-bottom: 1px solid var(--border-light);
      margin-bottom: 0;
    }
    .create-body {
      display: grid;
      gap: 10px;
      padding: 10px 15px 15px;
    }
    .create-body-inner {
      padding: 0;
    }
    .home-section {
      display: grid;
      gap: 14px;
    }
    .home-section .section-title { margin-bottom: 0; }
    .container-list { display: grid; gap: 14px; }
    .container-card {
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background:
        radial-gradient(circle at 18% 0%, rgba(139, 108, 247, 0.12), transparent 30%),
        linear-gradient(180deg, rgba(255,255,255,0.052), transparent 58%),
        var(--bg);
      padding: 18px;
      display: grid;
      gap: 16px;
      animation: enter 260ms var(--spring);
    }
    .container-top {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 18px;
      align-items: start;
    }
    .container-title {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      min-width: 0;
    }
    .container-title h3 { font-size: 22px; font-weight: 730; }
    .home-kicker {
      margin: 0 0 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 26px;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 3px 9px;
      background: var(--surface2);
      color: var(--muted);
      font-size: 13px;
      font-weight: 650;
      white-space: nowrap;
    }
    .status-badge::before {
      content: "";
      width: 7px;
      height: 7px;
      border-radius: 999px;
      background: currentColor;
      box-shadow: 0 0 16px currentColor;
    }
    .status-badge.ok { color: var(--ok); background: var(--ok-soft); border-color: rgba(99, 217, 140, 0.25); }
    .status-badge.warn { color: var(--warn); background: var(--warn-soft); border-color: rgba(242, 195, 107, 0.28); }
    .status-badge.err { color: var(--danger); background: var(--danger-soft); border-color: rgba(248, 113, 113, 0.28); }
    .container-actions {
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
    }
    .container-actions form { margin: 0; }
    .container-actions .button, .container-actions button { min-height: 38px; }
    .home-insights {
      display: grid;
      gap: 15px;
      border-top: 1px solid var(--border-light);
      padding-top: 15px;
    }
    .budget-card {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(160px, 34%);
      gap: 18px;
      align-items: end;
      border-radius: var(--radius);
      padding: 14px;
      background:
        linear-gradient(135deg, rgba(139, 108, 247, 0.13), rgba(16, 185, 129, 0.055)),
        color-mix(in srgb, var(--surface3) 88%, transparent);
    }
    .budget-copy {
      display: grid;
      gap: 4px;
      min-width: 0;
    }
    .metric-label, .metric-head span {
      color: var(--muted);
      font-size: 11px;
      font-weight: 720;
      text-transform: uppercase;
    }
    .budget-copy strong {
      color: var(--text);
      font-size: 36px;
      font-weight: 760;
      line-height: 1;
      font-variant-numeric: tabular-nums;
    }
    .budget-copy p {
      margin: 0;
      color: var(--muted);
      font-size: 12px;
    }
    .budget-meter {
      display: grid;
      gap: 8px;
      min-width: 0;
    }
    .budget-pair {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 10px;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }
    .budget-pair strong { color: var(--text); font-size: 15px; }
    .resource-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 0;
    }
    .metric-tile {
      padding: 2px 13px 0;
      display: grid;
      gap: 12px;
      min-width: 0;
      min-height: 118px;
    }
    .metric-tile:first-child { padding-left: 0; }
    .metric-tile + .metric-tile {
      border-left: 1px solid var(--border-light);
    }
    .metric-head {
      display: grid;
      gap: 3px;
      min-width: 0;
    }
    .metric-head strong {
      color: var(--text);
      font-size: 15px;
      font-weight: 740;
      font-variant-numeric: tabular-nums;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }
    .metric-bar {
      height: 9px;
      border-radius: 999px;
      background: var(--surface2);
      overflow: hidden;
    }
    .metric-bar > span {
      display: block;
      width: 0%;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--accent), #d8b4fe);
      transition: width 280ms ease;
    }
    .metric-tile:nth-child(2) .metric-bar > span { background: linear-gradient(90deg, #60a5fa, #8b6cf7); }
    .metric-tile:nth-child(3) .metric-bar > span { background: linear-gradient(90deg, #10b981, #7dd3fc); }
    .spark {
      width: 100%;
      height: 34px;
      display: block;
      overflow: visible;
    }
    .spark polyline {
      fill: none;
      stroke: color-mix(in srgb, var(--accent) 76%, white 12%);
      stroke-width: 2.2;
      stroke-linecap: round;
      stroke-linejoin: round;
      vector-effect: non-scaling-stroke;
    }
    .container-foot {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;
      color: var(--muted);
      font-size: 12px;
    }
    .container-foot span + span::before {
      content: "";
      width: 4px;
      height: 4px;
      display: inline-block;
      margin: 0 10px 2px 0;
      border-radius: 999px;
      background: var(--border);
    }
    .muted-line {
      color: var(--muted);
      font-size: 12px;
      margin-top: 5px;
    }
    @keyframes sweep {
      from { transform: translateX(-100%); }
      to { transform: translateX(240%); }
    }
    @keyframes enter {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: 1ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 1ms !important;
      }
    }
    @media (max-width: 860px) {
      .shell { padding: 18px 14px 48px; }
      .narrow { padding-top: 42px; }
      .login-shell { gap: 42px; padding-bottom: 24px; }
      .login-layout { grid-template-columns: 1fr; gap: 38px; }
      .login-story { max-width: 720px; }
      .login-story h2 { max-width: 12ch; font-size: clamp(42px, 10vw, 68px); }
      .login-card { max-width: 560px; order: -1; }
      .topbar { align-items: flex-start; flex-direction: column; }
      .actions { justify-content: flex-start; }
      .form-grid { grid-template-columns: 1fr; }
      .tier-grid { grid-template-columns: 1fr; }
      .trust-grid { grid-template-columns: 1fr; }
      .trust-strip, .billing-strip, .metric-grid { grid-template-columns: 1fr; }
      .instance { grid-template-columns: 1fr; }
      .instance-actions { min-width: 0; justify-content: flex-start; }
      .hero-panel { padding: 20px; }
      .launch-head, .container-top, .deploy-inline, .control-row { grid-template-columns: 1fr; }
      .container-actions {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(44px, 1fr));
        justify-content: stretch;
        width: 100%;
      }
      .container-actions .button, .container-actions button {
        width: 100%;
        min-width: 0;
        min-height: 44px;
        padding: 0;
      }
      .container-actions .button span { display: none; }
      .container-actions form {
        display: block;
        width: 100%;
      }
      .deploy-composer {
        grid-template-columns: 1fr;
        padding: 8px;
      }
      .deploy-button { width: 100%; }
      .limit-grid { grid-template-columns: 1fr; }
      .budget-card { grid-template-columns: 1fr; }
      .budget-copy strong { font-size: 30px; }
      .resource-grid { grid-template-columns: 1fr; }
      .metric-tile {
        min-height: 104px;
        padding: 13px 0 0;
      }
      .metric-tile:first-child { padding-top: 0; }
      .metric-tile + .metric-tile {
        border-left: 0;
        border-top: 1px solid var(--border-light);
      }
    }
    @media (max-width: 520px) {
      .login-shell { gap: 34px; }
      .login-topbar { align-items: flex-start; }
      .login-nav { gap: 12px; }
      .login-nav a:first-child { display: none; }
      .login-story h2 { font-size: clamp(38px, 13.5vw, 56px); letter-spacing: -0.03em; }
      .login-lead { margin-top: 18px; }
      .login-facts { margin-top: 22px; }
      .login-card-main { padding: 24px 20px; }
      .login-after { padding: 15px 20px; }
      .login-after ol { grid-template-columns: 1fr; gap: 7px; }
      .login-after li { grid-template-columns: 24px minmax(0, 1fr); gap: 4px; }
      .login-footer { align-items: flex-start; flex-direction: column; gap: 8px; }
    }
  </style>
</head>
<body>
  {{ body|safe }}
  <script>
    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-copy]");
      if (!button) return;
      const text = button.getAttribute("data-copy");
      navigator.clipboard.writeText(text).then(() => {
        const oldText = button.textContent;
        const oldTitle = button.getAttribute("title");
        const oldLabel = button.getAttribute("aria-label");
        button.classList.add("copied");
        button.setAttribute("title", "Copied");
        button.setAttribute("aria-label", "Copied");
        if (!button.classList.contains("icon")) button.textContent = "Copied";
        setTimeout(() => {
          button.classList.remove("copied");
          if (!button.classList.contains("icon")) button.textContent = oldText;
          if (oldTitle) button.setAttribute("title", oldTitle);
          if (oldLabel) button.setAttribute("aria-label", oldLabel);
        }, 1200);
      });
    });
  </script>
</body>
</html>
"""


def render(body):
    return render_template_string(
        LAYOUT,
        body=body,
        favicon_url=logo_url(),
        canonical_url=PUBLIC_CANONICAL_URL + path("/"),
    )


ICONS = {
    "copy": """<rect x="9" y="9" width="13" height="13" rx="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>""",
    "external": """<path d="M15 3h6v6"></path><path d="M10 14 21 3"></path><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"></path>""",
    "lifebuoy": """<circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="4"></circle><path d="m4.93 4.93 4.24 4.24"></path><path d="m14.83 14.83 4.24 4.24"></path><path d="m14.83 9.17 4.24-4.24"></path><path d="m4.93 19.07 4.24-4.24"></path>""",
    "plus": """<path d="M12 5v14"></path><path d="M5 12h14"></path>""",
    "refresh": """<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"></path><path d="M3 21v-5h5"></path><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"></path><path d="M16 8h5V3"></path>""",
    "trash": """<path d="M3 6h18"></path><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path><path d="M10 11v6"></path><path d="M14 11v6"></path>""",
    "train": """<path d="M6 15h12"></path><path d="M6 19h12"></path><path d="m8 19-2 3"></path><path d="m16 19 2 3"></path><path d="M8 3h8"></path><path d="M8 7h8"></path><rect x="5" y="3" width="14" height="16" rx="2"></rect><circle cx="9" cy="12" r="1"></circle><circle cx="15" cy="12" r="1"></circle>""",
}


def icon(name):
    return f"""<svg class="icon-svg" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>"""


def brand():
    return f"""
    <div class="brand">
      <img class="mark" src="{logo_url()}" alt="">
      <div>
        <h1>Möbius</h1>
        <p class="subtitle">Launch</p>
      </div>
    </div>
    """


def login_page():
    if google_oauth_configured():
        google_button = f"""
          <form method="post" action="{path('/auth/google')}">
            <button class="primary" type="submit">Continue with Google</button>
          </form>
        """
    elif email_login_enabled():
        google_button = ""
    else:
        google_button = """
          <button class="primary" type="button" disabled>Continue with Google</button>
          <p class="hint">Google OAuth is ready in the app, but this server still needs GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.</p>
        """
    provider_block = ""
    if google_button:
        provider_block = f"""
            <div class="provider-list">
              {google_button}
            </div>
        """
    email_fallback = ""
    if email_login_enabled():
        email_fallback = f"""
          <form method="post" action="{path('/login')}">
            <label>
              Email
              <input type="email" name="email" autocomplete="email" placeholder="you@example.com" required>
            </label>
            <button class="primary" type="submit">Continue</button>
          </form>
        """
    body = f"""
    <main class="shell login-shell">
      <header class="login-topbar">
        {brand()}
        <nav class="login-nav" aria-label="About Möbius">
          <a href="https://mobius-os.github.io/">What is Möbius?</a>
          <a href="https://github.com/mobius-os/mobius">Open source</a>
        </nav>
      </header>
      <section class="login-layout" aria-labelledby="login-heading">
        <div class="login-story">
          <p class="login-kicker">Community-built AGI, growing with its users</p>
          <h2 id="login-heading">Your own app-building workspace.</h2>
          <p class="login-lead">
            Turn repeated work into apps you keep. Use them on phone and web, personalize the
            workspace, and let memory and reflection improve the next loop.
          </p>
          <div class="login-facts" aria-label="What to expect from Möbius">
            <span>Apps for your work</span>
            <span>Phone and web</span>
            <span>Personalized over time</span>
          </div>
          <figure class="login-product-preview">
            <img src="{preview_url()}" alt="The Möbius App Store with community apps for skills, tasks, memory, reflection, and editing">
            <figcaption><strong>Inside Möbius</strong><span>Apps · productivity · personalization</span></figcaption>
          </figure>
        </div>
        <aside class="login-card" aria-label="Sign in to Möbius Launch">
          <div class="login-card-main">
            <p class="login-card-label">Launch dashboard</p>
            <h2>Start your private Möbius.</h2>
            <p class="login-card-copy">
              Sign in to create a deployment, check its status, and return to manage it later.
            </p>
            {provider_block}
            {email_fallback}
            <p class="login-trust">
              Your workspace stores its own conversations, files, apps, and agent activity.
              Möbius Launch only provisions and manages it.
            </p>
            <p class="login-requirement"><strong>Agent access:</strong> connect a ChatGPT plan with Codex access or a supported Claude Code plan inside your workspace.</p>
          </div>
          <div class="login-after">
            <strong>From the dashboard</strong>
            <ol aria-label="Launch steps">
              <li>Connect your Railway workspace</li>
              <li>Create and open your deployment</li>
              <li>Return anytime to manage it</li>
            </ol>
          </div>
        </aside>
      </section>
      <footer class="login-footer">
        <span>Möbius OS · Open source</span>
        <div class="login-footer-links">
          <a href="{path('/transparency')}">Data transparency</a>
          <a href="https://github.com/mobius-os/mobius">View the platform source</a>
        </div>
      </footer>
    </main>
    """
    return render(body)


@app.get("/")
def index():
    user = current_user()
    if user is None:
        return login_page()

    connection = get_connection(user["id"])
    connected = connection is not None
    oauth_ready = railway_oauth_configured()
    workspace = connection["railway_workspace_name"] if connection else ""
    source_kind, source_ref = mobius_source()

    disconnect_action = ""
    if connected:
        disconnect_action = f"""
        <form method="post" action="{path('/railway/disconnect')}">
          <button class="subtle" type="submit">Disconnect</button>
        </form>
        """

    top_status = ""
    if connected:
        top_status = f"""
        <span class="pill ok workspace-pill">{h(workspace or 'Railway connected')}</span>
        {disconnect_action}
        """

    if not connected:
        connection_notice = ""
        if not oauth_ready:
            connection_notice = f"""
            <div class="notice">
              Railway OAuth is wired in the app, but this server still needs RAILWAY_CLIENT_ID and RAILWAY_CLIENT_SECRET.
              <div class="command">{h(railway_redirect_uri())}</div>
            </div>
            """
        # Step 2 CTA: a real OAuth link when configured, disabled otherwise. The
        # ':not([disabled])' CSS keeps a disabled Connect from being promoted.
        if oauth_ready:
            connect_action = f"""
              <a class="button large step-cta step-connect" href="{path('/railway/connect')}">Connect Railway</a>
            """
        else:
            connect_action = """<button class="button large step-cta step-connect" type="button" disabled>Connect Railway</button>"""
        # Guided, not gated: opening step 1 marks it done and promotes step 2,
        # persisted in localStorage so it survives the round-trip to Railway. The
        # real gate for step 3 is the actual OAuth connection, not this flag. The
        # key is per-user so a shared browser doesn't show one account's progress
        # to the next.
        signup_flag_key = "mobius_railway_signup_opened:" + user["id"]
        stepper_script = """
        <script>
        (function () {
          var stepper = document.querySelector('[data-stepper]');
          if (!stepper) return;
          var KEY = '__KEY__';
          function promote() { stepper.classList.add('step1-done'); }
          try { if (localStorage.getItem(KEY) === '1') promote(); } catch (e) {}
          var trigger = stepper.querySelector('[data-step1]');
          if (trigger) {
            trigger.addEventListener('click', function () {
              try { localStorage.setItem(KEY, '1'); } catch (e) {}
              promote();
            });
          }
        })();
        </script>
        """.replace("__KEY__", signup_flag_key)
        body = f"""
        <main class="shell">
          <header class="topbar">
            {brand()}
            <div class="actions">
              <form method="post" action="{path('/logout')}">
                <button class="subtle" type="submit">Sign out</button>
              </form>
            </div>
          </header>
          <div class="stack">
            <section class="panel">
              <div class="launch-surface">
                <div class="launch-head">
                  <div class="launch-title">
                    <img class="launch-mark" src="{logo_url()}" alt="">
                    <div>
                      <p class="kicker">One-click Railway deployment</p>
                      <h2>Deploy Möbius.</h2>
                      <p class="hint">Three steps: create a Railway account, connect it, and deploy your private Möbius.</p>
                    </div>
                  </div>
                </div>
                <ol class="stepper" data-stepper>
                  <li class="step" data-step="1">
                    <span class="step-num">1</span>
                    <div class="step-body">
                      <div class="step-head">
                        <h3>Create your Railway account</h3>
                        <span class="step-done-badge">Opened &#8599;</span>
                      </div>
                      <p class="hint">Free for a month, no card needed. You'll accept Railway's terms here.</p>
                      <a class="button primary large step-cta step-create" href="{h(RAILWAY_SIGNUP_URL)}" target="_blank" rel="noopener noreferrer" data-step1>
                        <span>Create Railway account</span>{icon('external')}
                      </a>
                    </div>
                  </li>
                  <li class="step" data-step="2">
                    <span class="step-num">2</span>
                    <div class="step-body">
                      <h3>Connect Railway</h3>
                      <p class="hint">Authorize Möbius to deploy on your behalf. Already have a Railway account? You can start here.</p>
                      {connect_action}
                    </div>
                  </li>
                  <li class="step locked" data-step="3">
                    <span class="step-num">3</span>
                    <div class="step-body">
                      <h3>Deploy Möbius</h3>
                      <p class="hint">A private container in your Railway account, with persistent storage and live usage visibility. Unlocks once Railway is connected.</p>
                    </div>
                  </li>
                </ol>
                {connection_notice}
                <div class="signal-strip">
                  <span class="signal"><strong>1-month</strong> free trial</span>
                  <span class="signal">No card for trial</span>
                  <span class="signal">Email sign-in works</span>
                </div>
              </div>
            </section>
          </div>
        </main>
        {stepper_script}
        """
        return render(body)

    plan_state = get_plan_state(connection)
    plan_label = plan_state["plan_label"]
    deploy_blocked = plan_state["deploy_blocked"]
    limits = plan_limits(plan_label)
    plan_name = plan_title(plan_label)
    instances = list_instances(user["id"])
    rows = []
    for inst in instances:
        status = inst["status"] or "queued"
        pill_class = "ok" if status == "ready" else "err" if status in {"error", "delete_failed"} else "warn"
        status_label = status.replace("_", " ").title()
        step_text = inst["current_step"] or ""
        step_pill = (
            f"""<span class="pill" data-step>{h(step_text or 'created')}</span>"""
            if status != "ready" or (step_text and step_text.lower() != "ready")
            else """<span class="pill" data-step style="display: none;"></span>"""
        )
        open_action = (
            f"""<a class="button primary open-app" href="{h(inst['public_url'])}" target="_blank" rel="noreferrer" title="Open Möbius">{icon('external')}<span>Open</span></a>"""
            if inst["public_url"] and status not in {"error", "delete_failed", "deleted"}
            else f"""<button class="icon" type="button" disabled title="Möbius is not ready yet" aria-label="Möbius is not ready yet">{icon('external')}</button>"""
        )
        railway_url = (
            f"https://railway.com/project/{inst['railway_project_id']}"
            if inst["railway_project_id"]
            else ""
        )
        build_hint = (
            """<p class="hint">First builds can take a few minutes. You can close this page and come back; the dashboard will check Railway when you return.</p>"""
            if status in {"queued", "creating", "deploying"}
            else ""
        )
        error_markup = (
            f"""<div class="notice" style="margin-top: 10px;">{h(inst['last_error'])}</div>"""
            if inst["last_error"]
            else ""
        )
        railway_project_action = (
            f"""<a class="button subtle railway-link" href="{h(railway_url)}" target="_blank" rel="noreferrer" title="Open Railway project">{icon('train')}<span>Railway</span></a>"""
            if railway_url
            else ""
        )
        recovery_url = inst["recovery_url"] or (
            f"{inst['public_url'].rstrip('/')}/recover" if inst["public_url"] else ""
        )
        recovery_action = (
            f"""<a class="button subtle recovery-link" href="{h(recovery_url)}" target="_blank" rel="noreferrer" title="Open Möbius recovery">{icon('lifebuoy')}<span>Recovery</span></a>"""
            if recovery_url and status not in {"deleted"}
            else ""
        )
        delete_action = f"""<form method="post" action="{path('/instances/' + inst['id'] + '/delete')}" onsubmit="return confirm('Delete this Möbius and its Railway project? This cannot be undone.');">
                    <button class="danger icon" type="submit" title="Delete deployment" aria-label="Delete deployment">{icon('trash')}</button>
                  </form>"""
        retry_action = (
            f"""<form method="post" action="{path('/instances/' + inst['id'] + '/retry')}">
                    <button class="subtle icon" type="submit" title="Retry deployment" aria-label="Retry deployment">{icon('refresh')}</button>
                  </form>"""
            if status in {"error", "delete_failed"}
            else ""
        )
        cpu_cap = inst["cpu"] or ""
        memory_cap = inst["memory_mb"] or ""
        inst_plan = inst["plan_label"] or ""
        display_plan = plan_label if plan_label != "unknown" else inst_plan
        if cpu_cap or memory_cap:
            cap_parts = []
            if cpu_cap:
                cap_parts.append(f"{h(cpu_cap)} vCPU")
            if memory_cap:
                memory_label = memory_mb_label(memory_cap)
                if memory_label:
                    cap_parts.append(h(memory_label))
            caps_pill = f"""<span>Custom cap {' / '.join(cap_parts)}</span>"""
        else:
            caps_pill = f"""<span>Plan cap {h(plan_cap_label(display_plan))}</span>"""
        plan_pill = (
            f"""<span>{h(plan_title(display_plan))} plan</span>"""
            if display_plan
            else ""
        )
        poll_flag = "1" if status in {"queued", "creating", "deploying"} else "0"
        progress_markup = (
            """<div class="progress-line" aria-hidden="true"><span></span></div>"""
            if status in {"queued", "creating", "deploying"}
            else ""
        )
        metrics_markup = f"""
                <div class="home-insights" data-metrics-url="{path('/instances/' + inst['id'] + '/metrics')}">
                  <div class="budget-card">
                    <div class="budget-copy">
                      <span class="metric-label">Current spend</span>
                      <strong data-metric="cost-current">--</strong>
                      <p data-metric="cost-note">Current project usage to date. Billed by Railway.</p>
                    </div>
                    <div class="budget-meter">
                      <div class="metric-bar"><span data-meter="cost"></span></div>
                      <div class="budget-pair"><span>included trial</span><strong data-metric="cost-cap">$5</strong></div>
                    </div>
                  </div>
                  <div class="resource-grid">
                    <div class="metric-tile">
                      <div class="metric-head"><span>CPU</span><strong data-metric="cpu">--</strong></div>
                      <div class="metric-bar"><span data-meter="cpu"></span></div>
                      <svg class="spark" data-spark="cpu" viewBox="0 0 100 34" preserveAspectRatio="none"></svg>
                    </div>
                    <div class="metric-tile">
                      <div class="metric-head"><span>Memory</span><strong data-metric="memory">--</strong></div>
                      <div class="metric-bar"><span data-meter="memory"></span></div>
                      <svg class="spark" data-spark="memory" viewBox="0 0 100 34" preserveAspectRatio="none"></svg>
                    </div>
                    <div class="metric-tile">
                      <div class="metric-head"><span>Storage</span><strong data-metric="volume">{h(volume_size_label(inst['volume_size_gb']))}</strong></div>
                      <div class="metric-bar"><span data-meter="volume"></span></div>
                      <svg class="spark" data-spark="volume" viewBox="0 0 100 34" preserveAspectRatio="none"></svg>
                    </div>
                  </div>
                </div>
        """
        rows.append(
            f"""
            <article class="container-card" data-instance-id="{h(inst['id'])}" data-status="{h(status)}" data-poll="{poll_flag}">
              <div class="container-top">
                <div>
                  <p class="home-kicker">Private Railway container</p>
                  <div class="container-title">
                    <h3>{h(inst['display_name'])}</h3>
                    <span class="status-badge {pill_class}" data-pill>{h(status_label)}</span>
                    {step_pill}
                  </div>
                  {build_hint}
                  <div class="container-foot">
                    {plan_pill}
                    {caps_pill}
                    <span>{h(volume_size_label(inst['volume_size_gb']))} volume</span>
                  </div>
                  {error_markup}
                </div>
                <div class="container-actions">
                  {open_action}
                  {recovery_action}
                  {railway_project_action}
                  {retry_action}
                  {delete_action}
                </div>
              </div>
              {progress_markup}
              {metrics_markup}
                </article>
            """
        )

    instance_markup = "\n".join(rows)
    has_instances = bool(rows)

    connection_notice = ""
    if connection and connection["last_error"]:
        connection_notice = f"""
        <div class="notice">{h(connection['last_error'])}</div>
        """

    plan_copy = (
        "We couldn't read your Railway plan - you can still try to deploy."
        if plan_label == "unknown"
        else f"You're on the {plan_name} plan."
    )
    authorized_workspaces = live_connection_workspaces(connection)
    workspace_picker = ""
    if len(authorized_workspaces) > 1:
        workspace_picker = f"""
          <form method="post" action="{path('/railway/workspace')}" class="deploy-inline">
            <label class="input-shell">
              <span>Railway workspace</span>
              <select name="workspace_id">
                {workspace_select_options(authorized_workspaces, connection['railway_workspace_id'])}
              </select>
            </label>
            <button class="subtle" type="submit">Use workspace</button>
          </form>
        """
    elif not workspace:
        workspace_picker = """
          <div class="notice">Railway did not return an authorized workspace. Reconnect Railway and select a workspace during OAuth.</div>
        """
    memory_options = plan_memory_select_options(plan_label)
    volume_options = plan_volume_select_options(plan_label, plan_default_volume_gb(plan_label))
    plan_cap_copy = plan_cap_label(plan_label)
    if deploy_blocked:
        deploy_control = f"""
          <div class="notice">
            <p style="margin: 0 0 10px;">{h(deploy_blocked)}</p>
            <div class="actions left">
              <a class="button primary" href="https://railway.com/account/plans" target="_blank" rel="noreferrer">Manage plan on Railway</a>
              <button type="button" disabled>Deploy Möbius</button>
            </div>
          </div>
        """
    else:
        deploy_control = f"""
          <form class="deploy-card" method="post" action="{path('/instances')}">
            <div class="deploy-composer">
              <label class="deploy-name">
                <span>Name</span>
                <input name="display_name" value="My Möbius" maxlength="80" autocomplete="off" required>
              </label>
              <button class="primary deploy-button" type="submit">Deploy</button>
            </div>
            <details class="compact-details">
              <summary><span>Limits</span><small>{h(plan_cap_copy)}</small></summary>
              <div class="limit-grid">
                <label class="input-shell">
                  <span>CPU cap</span>
                  <input name="custom_cpu" type="number" inputmode="decimal" min="1" max="{limits['max_cpu']}" autocomplete="off" placeholder="Plan max">
                </label>
                <label class="input-shell">
                  <span>Memory</span>
                  <select name="memory_mb">
                    {memory_options}
                  </select>
                </label>
                <label class="input-shell">
                  <span>Storage</span>
                  <select name="volume_gb">
                    {volume_options}
                  </select>
                </label>
              </div>
              <p class="limits-note">Railway bills actual usage. These caps limit CPU/RAM; workspace hard limits stop spend.</p>
            </details>
          </form>
        """

    if has_instances:
        deploy_form = f"""
        <section id="new" class="panel create-panel">
          <details class="create-drawer">
            <summary>
              <span>
                <strong>New Möbius</strong>
                <span>{h(workspace or 'Railway workspace')} · {h(plan_copy)}</span>
              </span>
              <span class="create-plus" aria-hidden="true">{icon('plus')}</span>
            </summary>
            <div class="create-body">
              {connection_notice}
              {workspace_picker}
              <div class="create-body-inner">
                {deploy_control}
              </div>
            </div>
          </details>
        </section>
        """
    else:
        deploy_form = f"""
        <section id="new" class="panel">
          <div class="launch-surface">
            <div class="launch-head">
              <div class="launch-title">
                <img class="launch-mark" src="{logo_url()}" alt="">
                <div>
                  <h2>New Möbius</h2>
                  <p class="hint">{h(workspace or 'Railway workspace')} · {h(plan_copy)}</p>
                </div>
              </div>
                <div class="signal-strip">
                  <span class="signal"><strong>$5</strong> included</span>
                  <span class="signal">Usage-based</span>
                  <span class="signal">Hard limits stop spend</span>
                </div>
            </div>
            {connection_notice}
            {workspace_picker}
            <div class="create-body-inner">
              {deploy_control}
            </div>
          </div>
        </section>
        """

    # Live status: while any instance is still deploying, poll its status
    # endpoint (which reconciles from Railway) so the step advances and the page
    # reloads into the ready/error state without a manual refresh.
    poll_script = """
    <script>
    (function () {
      var base = "__BASE__";
      function setText(root, selector, value) {
        var el = root.querySelector(selector);
        if (el && value !== undefined && value !== null && value !== "") el.textContent = value;
      }
      function setMeter(root, selector, percent) {
        var el = root.querySelector(selector);
        if (!el) return;
        var value = parseFloat(String(percent || "").replace("%", ""));
        el.style.width = (isFinite(value) ? Math.max(0, Math.min(100, value)) : 0) + "%";
      }
      function setSpark(root, name, values) {
        var svg = root.querySelector('[data-spark="' + name + '"]');
        if (!svg || !Array.isArray(values) || !values.length) return;
        var points = values.map(function (raw, i) {
          var x = values.length === 1 ? 100 : (i / (values.length - 1)) * 100;
          var y = 22 - (Math.max(0, Math.min(100, Number(raw) || 0)) / 100) * 20;
          return x.toFixed(2) + "," + y.toFixed(2);
        }).join(" ");
        svg.innerHTML = '<polyline points="' + points + '"></polyline>';
      }
      function cpuPair(label, limit) {
        if (!limit || limit === 'n/a') return label;
        return String(label || '').replace(/ vCPU$/, '') + ' / ' + limit;
      }
      function loadMetrics() {
        document.querySelectorAll('[data-metrics-url]').forEach(function (el) {
          if (el.getAttribute('data-loading') === '1') return;
          el.setAttribute('data-loading', '1');
          fetch(el.getAttribute('data-metrics-url'), { headers: { 'Accept': 'application/json' } })
            .then(function (r) { return r.json().catch(function () { return null; }); })
            .then(function (d) {
              if (!d) return;
              if (d.cpu) {
                setText(el, '[data-metric="cpu"]', cpuPair(d.cpu.label, d.cpu.limit_label));
                setMeter(el, '[data-meter="cpu"]', d.cpu.percent);
                setSpark(el, 'cpu', d.cpu.spark);
              }
              if (d.memory) {
                setText(el, '[data-metric="memory"]', d.memory.label + (d.memory.limit_label && d.memory.limit_label !== 'n/a' ? ' / ' + d.memory.limit_label : ''));
                setMeter(el, '[data-meter="memory"]', d.memory.percent);
                setSpark(el, 'memory', d.memory.spark);
              }
              if (d.volume) {
                setText(el, '[data-metric="volume"]', d.volume.used_label + (d.volume.allocated_label && d.volume.allocated_label !== 'n/a' ? ' / ' + d.volume.allocated_label : ''));
                setMeter(el, '[data-meter="volume"]', d.volume.percent);
                setSpark(el, 'volume', d.volume.spark);
              }
              if (d.network) {
                setText(el, '[data-metric="network"]', (d.network.tx_label || '0') + ' out');
                setMeter(el, '[data-meter="network"]', d.network.percent);
                setSpark(el, 'network', d.network.spark);
              }
              if (d.cost) {
                setText(el, '[data-metric="cost-current"]', d.cost.label);
                setText(el, '[data-metric="cost-cap"]', d.cost.allowance_label || '$5');
                setText(el, '[data-metric="cost-note"]', d.cost.note);
                setMeter(el, '[data-meter="cost"]', d.cost.percent);
              }
              if (d.error) setText(el, '[data-metric="cost-note"]', d.error);
              var card = el.closest('.container-card');
              if (card && d.deployment_status && ['success', 'sleeping'].indexOf(String(d.deployment_status).toLowerCase()) !== -1 && card.getAttribute('data-status') !== 'ready') {
                location.reload();
              }
            })
            .catch(function () {})
            .finally(function () { el.removeAttribute('data-loading'); });
        });
      }
      function poll() {
        document.querySelectorAll('.container-card[data-poll="1"]').forEach(function (el) {
          var id = el.getAttribute('data-instance-id');
          fetch(base + '/instances/' + id + '/status', { headers: { 'Accept': 'application/json' } })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (d) {
              if (!d) return;
              var stepEl = el.querySelector('[data-step]');
              if (stepEl && d.current_step) stepEl.textContent = d.current_step;
              if (d.status !== el.getAttribute('data-status')) location.reload();
            })
            .catch(function () {});
        });
        loadMetrics();
      }
      loadMetrics();
      if (document.querySelector('.container-card[data-poll="1"]')) setInterval(poll, 5000);
      if (document.querySelector('[data-metrics-url]')) setInterval(loadMetrics, 30000);
    })();
    </script>
    """.replace("__BASE__", APP_BASE_PATH)

    instances_panel = ""
    if rows:
        instances_panel = f"""
    <section class="home-section">
      <div class="section-title">
        <h2>Your Möbius</h2>
      </div>
      <div class="container-list">{instance_markup}</div>
    </section>
    {poll_script}
    """

    main_content = f"{instances_panel}{deploy_form}" if has_instances else f"{deploy_form}{instances_panel}"

    body = f"""
    <main class="shell">
      <header class="topbar">
        {brand()}
        <div class="actions">
          {top_status}
          <form method="post" action="{path('/logout')}">
            <button class="subtle" type="submit">Sign out</button>
          </form>
        </div>
      </header>
      <div class="stack">{main_content}</div>
    </main>
    """
    return render(body)


@app.get("/transparency")
def transparency():
    user = current_user()
    back_url = path("/") if user else path("/")
    body = f"""
    <main class="shell">
      <header class="topbar">
        {brand()}
        <div class="actions">
          <a class="button subtle" href="{back_url}">Back</a>
        </div>
      </header>
      <div class="stack">
        <section class="panel">
          <div class="section">
            <div class="section-title">
              <div>
                <h2>What Möbius Launch Stores</h2>
                <p class="hint">The launcher is a bridge between your Möbius account and your Railway-owned deployments. It keeps the minimum state needed to reconnect, resume, and delete what it created.</p>
              </div>
            </div>
            <div class="trust-grid">
              <div class="trust-card">
                <h3>Stored</h3>
                <ul>
                  <li>Your Möbius Launch account email, name, sign-in provider, and avatar URL when available.</li>
                  <li>An encrypted Railway OAuth token so deployments can be created and refreshed.</li>
                  <li>Deployment metadata: Railway project, service, environment, volume, public URL, recovery URL, and selected resource caps.</li>
                  <li>Short provisioning events and errors so failed launches are debuggable.</li>
                </ul>
              </div>
              <div class="trust-card">
                <h3>Fetched live</h3>
                <ul>
                  <li>Railway workspace choices and deployment status are refreshed from Railway when the page needs them.</li>
                  <li>CPU, RAM, disk, volume, and network metrics are read on demand and not persisted as history.</li>
                  <li>Exact billing and usage limits stay in Railway; the launcher links you to the Railway project for spend details.</li>
                </ul>
              </div>
              <div class="trust-card">
                <h3>Never stored</h3>
                <ul>
                  <li>Your Möbius conversations, files, apps, databases, or agent activity.</li>
                  <li>Your Railway password or Google password.</li>
                  <li>Product analytics or telemetry from inside your Möbius instance.</li>
                </ul>
              </div>
            </div>
          </div>
          <div class="section">
            <h2>Backend Surface</h2>
            <p class="hint">The backend is intentionally small: OAuth callbacks, encrypted token storage, a deploy worker, and a deployment registry.</p>
            <div class="meta">
              <span class="pill">OAuth callbacks</span>
              <span class="pill">Encrypted tokens</span>
              <span class="pill">Template deploy worker</span>
              <span class="pill">Deployment registry</span>
            </div>
          </div>
        </section>
      </div>
    </main>
    """
    return render(body)


@app.post("/login")
def login():
    if not email_login_enabled():
        return redirect(path("/"))
    email = request.form.get("email", "").strip().lower()
    if not email:
        return redirect(path("/"))
    existing = db().execute(
        "select auth_provider from users where email = ?", (email,)
    ).fetchone()
    if existing and existing["auth_provider"] != "prototype-email":
        # Never let the passwordless fallback resolve to an account created via a
        # real provider (e.g. Google). That would be an account takeover.
        return oauth_error(
            "Use your original sign-in",
            "This email is already registered with a different sign-in method.",
        )
    user_id = upsert_user(
        email=email,
        name=email.split("@", 1)[0],
        provider="prototype-email",
        provider_subject=email,
    )
    resp = make_response(redirect(path("/")))
    return set_session(resp, user_id)


@app.post("/auth/google")
def google_login():
    if not google_oauth_configured():
        return redirect(path("/"))
    redirect_uri = google_redirect_uri()
    state = google_state_serializer.dumps(
        {"nonce": secrets.token_urlsafe(16), "iat": int(time.time()), "redirect_uri": redirect_uri}
    )
    params = {
        "response_type": "code",
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    resp = make_response(redirect(GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)))
    resp.set_cookie(
        "google_oauth_state",
        state,
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=10 * 60,
        path=APP_BASE_PATH or "/",
    )
    return resp


@app.get("/auth/google/callback")
def google_callback():
    if request.args.get("error"):
        return oauth_error(
            "Google did not connect",
            request.args.get("error_description") or request.args.get("error"),
        )
    state = request.args.get("state", "")
    cookie_state = request.cookies.get("google_oauth_state", "")
    if not state or not cookie_state or not secrets.compare_digest(state, cookie_state):
        return oauth_error("Google did not connect", "The OAuth state check failed.")
    try:
        payload = google_state_serializer.loads(state, max_age=10 * 60)
    except SignatureExpired:
        return oauth_error("Google did not connect", "The OAuth request expired.")
    except BadSignature:
        return oauth_error("Google did not connect", "The OAuth state was invalid.")

    code = request.args.get("code")
    if not code:
        return oauth_error("Google did not connect", "Google did not return a code.")
    try:
        tokens = oauth_form_post(
            GOOGLE_TOKEN_URL,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": payload.get("redirect_uri") or google_redirect_uri(),
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
            },
        )
        access_token = tokens.get("access_token")
        if not access_token:
            raise RailwayAPIError("Google did not return an access token.")
        profile = railway_get_json(GOOGLE_USERINFO_URL, access_token)
        if str(profile.get("email_verified")).lower() not in {"1", "true", "yes"}:
            raise RailwayAPIError("Your Google email address is not verified.")
        email = profile.get("email")
        if not email:
            raise RailwayAPIError("Google did not return an email address.")
        user_id = upsert_user(
            email=email,
            name=profile.get("name") or email.split("@", 1)[0],
            provider="google",
            provider_subject=profile.get("sub") or email,
            avatar_url=profile.get("picture"),
        )
    except RailwayAPIError as exc:
        return oauth_error("Google did not connect", str(exc))

    resp = make_response(redirect(path("/")))
    resp.delete_cookie("google_oauth_state", path=APP_BASE_PATH or "/")
    return set_session(resp, user_id)


@app.post("/logout")
def logout():
    resp = make_response(redirect(path("/")))
    resp.delete_cookie("railway_oauth_state", path=APP_BASE_PATH or "/")
    resp.delete_cookie("google_oauth_state", path=APP_BASE_PATH or "/")
    return clear_session(resp)


@app.route("/railway/connect", methods=["GET", "POST"])
def connect_railway():
    user = require_user()
    if user is None:
        return redirect(path("/"))
    if not railway_oauth_configured():
        return redirect(path("/"))

    code_verifier = secrets.token_urlsafe(64)
    redirect_uri = railway_redirect_uri()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")
    state = oauth_state_serializer.dumps(
        {
            "user_id": user["id"],
            "nonce": secrets.token_urlsafe(16),
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
        }
    )
    params = {
        "response_type": "code",
        "client_id": RAILWAY_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": RAILWAY_OAUTH_SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if "offline_access" in RAILWAY_OAUTH_SCOPES.split():
        params["prompt"] = "consent"
    # No referralCode here: Railway ignores it on the authorize endpoint. The
    # referral attaches when the user creates their account (onboarding step 1,
    # RAILWAY_SIGNUP_URL), which is also where Railway shows its ToS.

    auth_url = RAILWAY_AUTH_URL + "?" + urllib.parse.urlencode(params)
    resp = make_response(redirect(auth_url))
    resp.set_cookie(
        "railway_oauth_state",
        state,
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=10 * 60,
        path=APP_BASE_PATH or "/",
    )
    return resp


@app.get("/railway/callback")
def railway_callback():
    user = require_user()
    if user is None:
        return redirect(path("/"))
    if request.args.get("error"):
        return oauth_error(
            "Railway did not connect",
            request.args.get("error_description") or request.args.get("error"),
        )

    state = request.args.get("state", "")
    cookie_state = request.cookies.get("railway_oauth_state", "")
    if not state or not cookie_state or not secrets.compare_digest(state, cookie_state):
        return oauth_error("Railway did not connect", "The OAuth state check failed.")
    try:
        payload = oauth_state_serializer.loads(state, max_age=10 * 60)
    except SignatureExpired:
        return oauth_error("Railway did not connect", "The OAuth request expired.")
    except BadSignature:
        return oauth_error("Railway did not connect", "The OAuth state was invalid.")
    if payload.get("user_id") != user["id"]:
        return oauth_error("Railway did not connect", "The OAuth session user changed.")

    code = request.args.get("code")
    if not code:
        return oauth_error("Railway did not connect", "Railway did not return a code.")

    try:
        tokens = exchange_railway_code(
            code,
            payload.get("redirect_uri") or railway_redirect_uri(),
            payload.get("code_verifier"),
        )
        access_token = tokens.get("access_token")
        if not access_token:
            raise RailwayAPIError("Railway did not return an access token.")
        profile = railway_get_json(RAILWAY_ME_URL, access_token)
        workspace_error = None
        try:
            workspaces = fetch_railway_workspaces(access_token)
        except RailwayAPIError as exc:
            workspaces = []
            workspace_error = f"Connected to Railway, but workspace lookup failed: {exc}"
        save_oauth_connection(user, profile, workspaces, tokens, workspace_error)
    except RailwayAPIError as exc:
        return oauth_error("Railway did not connect", str(exc))

    resp = make_response(redirect(path("/")))
    resp.delete_cookie("railway_oauth_state", path=APP_BASE_PATH or "/")
    return resp


@app.post("/railway/disconnect")
def disconnect_railway():
    user = require_user()
    if user is None:
        return redirect(path("/"))
    db().execute("delete from railway_connections where user_id = ?", (user["id"],))
    db().commit()
    return redirect(path("/"))


@app.post("/railway/workspace")
def select_railway_workspace():
    user = require_user()
    if user is None:
        return redirect(path("/"))
    connection = get_connection(user["id"])
    if connection is None:
        return redirect(path("/"))
    workspace_id = (request.form.get("workspace_id") or "").strip()
    workspaces = live_connection_workspaces(connection)
    workspace = next((item for item in workspaces if item["id"] == workspace_id), None)
    if workspace is None:
        return oauth_error("Workspace not available", "Reconnect Railway and authorize the workspace you want to use.")
    timestamp = now_iso()
    db().execute(
        """
        update railway_connections
        set railway_workspace_id = ?, railway_workspace_name = ?,
            cached_plan = null, deploy_blocked = '', plan_checked_at = null,
            updated_at = ?
        where id = ?
        """,
        (workspace["id"], workspace["name"], timestamp, connection["id"]),
    )
    db().commit()
    return redirect(path("/#new"), code=303)


@app.get("/railway/template")
def railway_template():
    user = require_user()
    if user is None:
        return redirect(path("/"))
    if not RAILWAY_TEMPLATE_URL:
        return redirect(path("/"))
    return redirect(RAILWAY_TEMPLATE_URL)


@app.post("/instances")
def create_instance():
    user = require_user()
    if user is None:
        return redirect(path("/"))
    connection = get_connection(user["id"])
    if connection is None or connection["connected_mode"] != "oauth":
        return redirect(path("/"))

    display_name = (request.form.get("display_name") or "My Möbius").strip()[:80]
    # handle is an internal label only; Railway assigns the real public domain.
    handle = normalize_handle(display_name)
    auth_mode = "local"  # the instance uses its own username/password on first open
    state = get_plan_state(connection)
    if state["deploy_blocked"]:
        return oauth_error("Railway plan required", state["deploy_blocked"])
    limits = plan_limits(state["plan_label"])
    default_volume_gb = plan_default_volume_gb(state["plan_label"])
    volume_gb = coerce_volume_size_gb(request.form.get("volume_gb"), default_volume_gb) or default_volume_gb
    min_volume_gb = min(limits["volume_options_gb"])
    volume_gb = max(min_volume_gb, min(limits["max_volume_gb"], float(volume_gb)))
    custom_cpu_raw = (request.form.get("custom_cpu") or "").strip()
    custom_cpu = (
        None
        if not custom_cpu_raw
        else clamped_int(custom_cpu_raw, limits["max_cpu"], 1, limits["max_cpu"])
    )
    memory_mb_raw = (request.form.get("memory_mb") or "").strip()
    memory_mb = (
        None
        if not memory_mb_raw
        else clamped_int(memory_mb_raw, limits["max_memory_mb"], 128, limits["max_memory_mb"])
    )

    timestamp = now_iso()
    instance_id = "mob_" + uuid.uuid4().hex[:10]
    source_kind, source_ref = mobius_source()
    db().execute(
        """
        insert into mobius_instances (
          id, user_id, railway_connection_id, display_name, handle, status,
          railway_project_id, railway_environment_id, railway_service_id,
          railway_volume_id, railway_domain, public_url, recovery_url,
          auth_mode, image_ref, source_kind, source_ref, volume_size_gb,
          cpu, memory_mb, plan_label, railway_project_name, railway_workspace_name, current_step,
          last_error, last_deployment_id, created_at, updated_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            instance_id,
            user["id"],
            connection["id"],
            display_name,
            handle,
            "queued",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            auth_mode,
            source_ref,
            source_kind,
            source_ref,
            format_volume_gb(volume_gb),
            str(custom_cpu) if custom_cpu else "",
            str(memory_mb) if memory_mb else "",
            state["plan_label"],
            display_name,
            connection["railway_workspace_name"],
            "Queued",
            None,
            None,
            timestamp,
            timestamp,
        ),
    )
    add_instance_event(db(), instance_id, "info", "Deployment queued")
    db().commit()
    start_provisioning(instance_id)
    return redirect(path("/#new"), code=303)


@app.get("/instances/<instance_id>/status")
def instance_status(instance_id):
    user = require_user()
    if user is None:
        return Response('{"error":"unauthorized"}', status=401, mimetype="application/json")
    inst = db().execute(
        "select * from mobius_instances where id = ? and user_id = ?",
        (instance_id, user["id"]),
    ).fetchone()
    if inst is None:
        return Response('{"error":"not found"}', status=404, mimetype="application/json")
    if inst["status"] in {"queued", "creating"}:
        include_creating = inst["status"] == "creating"
        stale = timestamp_age_seconds(inst["updated_at"]) > PROVISIONING_STALE_SECONDS
        if inst["status"] == "queued" or stale:
            if start_provisioning(inst["id"], include_creating=include_creating):
                inst = db().execute(
                    "select * from mobius_instances where id = ? and user_id = ?",
                    (instance_id, user["id"]),
                ).fetchone()
    inst = reconcile_deployment_status(db(), inst)
    return {
        "id": inst["id"],
        "status": inst["status"],
        "current_step": inst["current_step"],
        "public_url": inst["public_url"],
        "last_error": inst["last_error"],
    }


@app.get("/instances/<instance_id>/metrics")
def instance_metrics(instance_id):
    user = require_user()
    if user is None:
        return Response('{"error":"unauthorized"}', status=401, mimetype="application/json")
    inst = db().execute(
        "select * from mobius_instances where id = ? and user_id = ?",
        (instance_id, user["id"]),
    ).fetchone()
    if inst is None:
        return Response('{"error":"not found"}', status=404, mimetype="application/json")
    if not (
        inst["railway_project_id"]
        and inst["railway_service_id"]
        and inst["railway_environment_id"]
    ):
        return {
            "updated_at": now_iso(),
            "deployment_status": inst["status"],
            "error": "Railway has not returned deployment resources yet.",
        }
    connection = db().execute(
        "select * from railway_connections where id = ? and user_id = ?",
        (inst["railway_connection_id"], user["id"]),
    ).fetchone()
    if connection is None:
        return Response('{"error":"Railway is not connected"}', status=409, mimetype="application/json")
    try:
        access_token = refresh_railway_access_token(connection, db())
        inst = reconcile_deployment_status(db(), inst)
        return railway_metrics_snapshot(access_token, connection, inst)
    except RailwayAPIError as exc:
        message = user_facing_railway_error(exc)
        status = 202 if service_instance_missing_error(exc) else 502
        return {
            "updated_at": now_iso(),
            "deployment_status": inst["status"],
            "error": message,
            "cost": {
                "available": False,
                "label": "Pending" if status == 202 else "Railway",
                "allowance_label": "$5",
                "percent": "0%",
                "note": message if status == 202 else "Open Railway for detailed usage and cost.",
            },
        }, status


@app.post("/instances/<instance_id>/retry")
def retry_instance(instance_id):
    user = require_user()
    if user is None:
        return redirect(path("/"))
    inst = db().execute(
        "select * from mobius_instances where id = ? and user_id = ?",
        (instance_id, user["id"]),
    ).fetchone()
    if inst is None or inst["status"] == "deleted":
        return redirect(path("/"))
    if inst["status"] not in {"error", "delete_failed", "creating", "deploying"}:
        return redirect(path("/"))
    update_instance(
        db(),
        inst["id"],
        status="queued",
        current_step="Retrying Railway deployment",
        last_error="",
        provision_token="",
    )
    add_instance_event(db(), inst["id"], "info", "Retry requested")
    db().commit()
    start_provisioning(inst["id"])
    return redirect(path("/"))


@app.post("/instances/<instance_id>/delete")
def delete_instance(instance_id):
    user = require_user()
    if user is None:
        return redirect(path("/"))
    inst = db().execute(
        "select * from mobius_instances where id = ? and user_id = ?",
        (instance_id, user["id"]),
    ).fetchone()
    if inst is None:
        return redirect(path("/"))
    update_instance(db(), instance_id, status="deleted", current_step="Deleting", provision_token="")
    add_instance_event(db(), instance_id, "info", "Delete requested")
    db().commit()
    if inst["railway_project_id"]:
        connection = db().execute(
            "select * from railway_connections where id = ?",
            (inst["railway_connection_id"],),
        ).fetchone()
        try:
            if connection is None:
                raise RailwayAPIError("Railway is not connected.")
            access_token = refresh_railway_access_token(connection, db())
            delete_project(access_token, inst["railway_project_id"])
        except RailwayAPIError:
            update_instance(
                db(),
                instance_id,
                status="delete_failed",
                current_step="Delete failed",
                provision_token="",
                last_error="Could not delete the Railway project. Try again, or delete it from Railway.",
            )
            add_instance_event(
                db(),
                instance_id,
                "error",
                "Could not delete the Railway project. Try again, or delete it from Railway.",
            )
            db().commit()
            return redirect(path("/#new"), code=303)
    update_instance(db(), instance_id, status="deleted", current_step="Deleted", provision_token="")
    add_instance_event(db(), instance_id, "info", "Instance deleted")
    db().commit()
    return redirect(path("/#new"), code=303)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "mobius-launch",
        "source_repo": MOBIUS_LAUNCH_SOURCE_REPO,
        "git_sha": MOBIUS_LAUNCH_GIT_SHA,
    }


@app.get("/version")
def version():
    return build_info()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
