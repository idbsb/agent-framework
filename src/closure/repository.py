"""Read-only access to the existing P1 publication snapshots, never draft versions."""
import json
import os
import sqlite3
from pathlib import Path


class ProfileReadError(RuntimeError):
    """Fail explicitly instead of silently scoring against an obsolete baseline."""


def closure_database_path(project_root):
    root = Path(project_root).resolve()
    path = Path(os.getenv("P1_CLOSURE_DB", str(root / "data/p1_closure.sqlite3"))).resolve()
    if root not in path.parents or path.suffix != ".sqlite3":
        raise ProfileReadError("P1 database must be a project-local .sqlite3 companion file")
    return path


class PublishedProfileRepository:
    def __init__(self, path):
        self.path = path  # Path or callable; no connection/cache created at startup.

    def latest_by_job(self):
        path = Path(self.path() if callable(self.path) else self.path)
        if not path.exists():
            return {}
        try:
            conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
            try:
                rows = conn.execute("SELECT kind,id,payload FROM entities ORDER BY kind,id").fetchall()
            finally:
                conn.close()
            candidates, profiles = {}, {}
            for kind, identifier, payload in rows:
                entity = json.loads(payload)
                # legacy_baseline is initialized by recompute, not approved/published by a person.
                publications = [p for p in entity["publications"] if p.get("status") == "published" and p.get("origin") == "human_approved"]
                if not publications:
                    continue
                latest = max(publications, key=lambda p: int(p["profile_version"]))
                definition = latest.get("manual_definition") or latest["auto_definition"]
                title = identifier if kind == "profile" else definition["job_name"]
                value = dict(latest, entity_kind=kind, entity_id=identifier)
                target = profiles if kind == "profile" else candidates
                if title in target:
                    raise ProfileReadError("Ambiguous published job name; reconcile candidate identities before use")
                target[title] = value
            # An existing standard-role profile is authoritative over a same-name candidate.
            return {**candidates, **profiles}
        except (sqlite3.Error, ValueError, KeyError, TypeError) as exc:
            raise ProfileReadError("Published profile store cannot be read safely") from exc
