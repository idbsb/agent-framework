"""One configuration contract for closure writers and published-profile readers."""
import os
from pathlib import Path
from urllib.parse import urlsplit


class ProfileReadError(RuntimeError):
    """Fail closed when the formal profile store is unavailable."""


def free_readonly():
    """Allow a Render Free demo only when the P1 write switch is off.

    Render Free has no persistent disk.  This mode intentionally falls back to
    the frozen repository data and never presents ephemeral SQLite writes as
    durable production data.
    """
    requested = os.getenv("P1_FREE_READONLY") == "1"
    safe_render_default = (os.getenv("RENDER") == "true"
                           and not os.getenv("P1_STORAGE_DIR"))
    return (requested or safe_render_default) and os.getenv("P1_CLOSURE_WRITES") != "1"


def production():
    mode = os.getenv("P1_ENV", "local")
    if mode not in {"local", "production"}:
        raise ProfileReadError("P1_ENV must be local or production")
    if free_readonly():
        return False
    return mode == "production" or os.getenv("RENDER") == "true"


def allowed_origins():
    origins = [v.strip().rstrip("/") for v in os.getenv("CORS_ORIGINS", "").split(",") if v.strip()]
    if production():
        if not origins:
            raise ProfileReadError("Production requires explicit CORS_ORIGINS")
        for origin in origins:
            url = urlsplit(origin)
            if (url.scheme != "https" or not url.hostname or url.username or url.password
                    or url.path or url.query or url.fragment or "*" in origin
                    or url.hostname in {"localhost", "127.0.0.1", "::1"}):
                raise ProfileReadError("Production CORS_ORIGINS must contain exact HTTPS origins")
    else:
        origins += ["http://127.0.0.1:5173", "http://localhost:5173"]
    return list(dict.fromkeys(origins))


def validate_auth():
    if not production():
        return
    allowed_origins()
    token = os.getenv("P1_ADMIN_TOKEN", "")
    if len(token) < 32 or not token.isascii() or any(c.isspace() for c in token):
        raise ProfileReadError("Production requires a random P1_ADMIN_TOKEN of at least 32 ASCII characters")
    if not os.getenv("P1_ADMIN_NAME", "").strip():
        raise ProfileReadError("Production requires P1_ADMIN_NAME for audit attribution")


def closure_database_path(project_root):
    root = Path(project_root).resolve()
    raw = os.getenv("P1_CLOSURE_DB", "")
    if production():
        storage_raw = os.getenv("P1_STORAGE_DIR", "")
        if not storage_raw or not Path(storage_raw).is_absolute() or not raw or not Path(raw).is_absolute():
            raise ProfileReadError("Production requires absolute P1_STORAGE_DIR and P1_CLOSURE_DB")
        storage = Path(storage_raw).resolve()
        path = Path(raw).resolve()
        if not storage.is_dir() or storage == root or root in storage.parents:
            raise ProfileReadError("Production storage must be an existing directory outside the checkout")
        if storage not in path.parents or path.suffix != ".sqlite3":
            raise ProfileReadError("Production database must be a .sqlite3 file within P1_STORAGE_DIR")
        # Render must actually mount the disk; an ephemeral directory is not sufficient.
        if os.getenv("RENDER") == "true" and not os.path.ismount(storage):
            raise ProfileReadError("Render persistent disk is not mounted at P1_STORAGE_DIR")
        return path
    path = (root / raw).resolve() if raw else root / "data/p1_closure.sqlite3"
    if root not in path.parents or path.suffix != ".sqlite3":
        raise ProfileReadError("Local P1 database must be a project-local .sqlite3 companion file")
    return path
