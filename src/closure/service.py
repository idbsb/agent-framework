import copy
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from ..emerging.emerging_job_detector import EmergingJobDetector
from .settings import production, ProfileReadError
from .evidence import definition, definition_diff, fingerprint, load_records, normalize_record, skills_for


class ClosureError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def now():
    return datetime.now(timezone.utc).isoformat()


class ClosureService:
    """Local companion store, not a migration of frozen data or P0 scoring.

    BEGIN IMMEDIATE serializes read-modify-write; expected version/revision prevents lost edits.
    Content versions and publication snapshots are immutable. Reviews append audit events.
    """
    def __init__(self, core, db_path, base_records=None):
        self.core = core
        self.db_path = Path(db_path)
        initialize = not self.db_path.exists()
        if production() and initialize:
            if os.getenv("P1_INITIALIZE_DB") != "1":
                raise ProfileReadError("Production database missing; explicit first-time initialization required")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if production() and not self.db_path.exists():
            sqlite3.connect(self.db_path).close()  # explicitly authorized first-time bootstrap only
        self.base = load_records(core) if base_records is None else [normalize_record(r, core.skill_index) for r in base_records]
        self.detector = EmergingJobDetector(core.loader, core.skill_index)
        root = core.loader.project_root
        self.evolution = yaml.safe_load((root / "external_modules/graph_dynamic/config/evolution_config.yaml").read_text(encoding="utf-8"))
        self.matching = yaml.safe_load((root / "config/matching_weights.yaml").read_text(encoding="utf-8"))["profile"]
        with self._db() as conn:
            if production() and not initialize:
                # Existing production stores must have the schema; do not silently repair data loss.
                conn.execute("SELECT id,payload FROM evidence LIMIT 0")
                conn.execute("SELECT kind,id,payload FROM entities LIMIT 0")
            conn.execute("CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS entities (kind TEXT, id TEXT, payload TEXT NOT NULL, PRIMARY KEY(kind,id))")

    @contextmanager
    def _db(self):
        target = self.db_path.resolve().as_uri() + "?mode=rw" if production() else self.db_path
        conn = sqlite3.connect(target, uri=production(), timeout=10)
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def check_storage(self):
        try:
            conn = sqlite3.connect(self.db_path.resolve().as_uri() + "?mode=rw", uri=True, timeout=10)
            try:
                conn.execute("BEGIN IMMEDIATE")
                if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise ProfileReadError("Closure storage integrity check failed")
                conn.execute("SELECT id,payload FROM evidence LIMIT 1").fetchall()
                conn.execute("SELECT kind,id,payload FROM entities LIMIT 1").fetchall()
                conn.execute("UPDATE evidence SET payload=payload WHERE 0")
            finally:
                conn.rollback()
                conn.close()
        except sqlite3.Error as exc:
            raise ProfileReadError("Closure storage is unavailable") from exc

    def _records(self, conn):
        return sorted(self.base + [json.loads(r[0]) for r in conn.execute("SELECT payload FROM evidence")], key=lambda r: r["job_id"])

    def _read(self, conn, kind, identifier):
        if kind not in {"candidate", "profile"}:
            raise ClosureError(400, "invalid kind")
        row = conn.execute("SELECT payload FROM entities WHERE kind=? AND id=?", (kind, identifier)).fetchone()
        return json.loads(row[0]) if row else None

    def _save(self, conn, entity):
        conn.execute("INSERT INTO entities VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload",
                     (entity["kind"], entity["id"], json.dumps(entity, ensure_ascii=False)))

    @staticmethod
    def _entity(kind, identifier, anchor=None):
        return dict(kind=kind, id=identifier, anchor=anchor, versions=[], publications=[], events=[])

    @staticmethod
    def _latest(entity):
        if not entity or not entity["versions"]:
            raise ClosureError(404, "not found")
        return entity["versions"][-1]

    def _check(self, entity, version, revision):
        current = self._latest(entity)
        if (current["version"], current["revision"]) != (version, revision):
            raise ClosureError(409, "version conflict; reload latest version")
        return current

    def _append(self, entity, snapshot, status):
        latest = entity["versions"][-1] if entity["versions"] else None
        content_hash = fingerprint(snapshot)
        if latest and latest["fingerprint"] == content_hash:
            return latest
        item = dict(snapshot, kind=entity["kind"], id=entity["id"], version=len(entity["versions"])+1,
                    previous_version=latest["version"] if latest else None, revision=0, status=status,
                    created_at=now(), fingerprint=content_hash, reviewed_at=None, reviewer=None, review_note=None)
        entity["versions"].append(item)
        entity["events"].append(dict(event="new_version", version=item["version"], at=item["created_at"]))
        return item

    def add_evidence(self, raw):
        row = normalize_record(raw, self.core.skill_index)
        if not row["job_id"] or not row["original_title"]:
            raise ClosureError(422, "job_id and original_title required")
        with self._db() as conn:
            prior = next((r for r in self._records(conn) if r["job_id"] == row["job_id"]), None)
            if prior is not None:
                if prior != row:
                    raise ClosureError(409, "JD id already exists with different evidence; originals cannot be overwritten")
                return prior
            conn.execute("INSERT INTO evidence VALUES (?,?)", (row["job_id"], json.dumps(row, ensure_ascii=False)))
        return row

    def evidence(self, identifier):
        with self._db() as conn:
            row = next((r for r in self._records(conn) if r["job_id"] == identifier), None)
            if row is None:
                raise ClosureError(404, "job evidence not found")
            return row

    def list_entities(self, kind):
        with self._db() as conn:
            return [self._latest(json.loads(r[0])) for r in conn.execute("SELECT payload FROM entities WHERE kind=? ORDER BY id", (kind,))]

    def get(self, kind, identifier):
        with self._db() as conn:
            return self._latest(self._read(conn, kind, identifier))

    def history(self, kind, identifier):
        with self._db() as conn:
            entity = self._read(conn, kind, identifier)
            self._latest(entity)
            return entity

    def published(self, kind, identifier):
        with self._db() as conn:
            entity = self._read(conn, kind, identifier)
            if not entity or not entity["publications"]:
                raise ClosureError(404, "no published profile")
            return entity["publications"][-1]

    def discover(self):
        with self._db() as conn:
            rows = self._records(conn)
            by_id = {r["job_id"]: r for r in rows}
            records = [dict(r, jd_id=r["job_id"], original_job_title=r["original_title"], source_url=r["url"],
                            skill_ids={s["skill_id"] for s in r["skill_evidence"] if s["accepted"] and s["polarity"] == "affirmed"},
                            published_date=date.fromisoformat(r["published_at"][:10]) if r["published_at"] else None) for r in rows]
            class EvidenceDetector(EmergingJobDetector):
                def _records(self):
                    return records
            detected = EvidenceDetector(self.core.loader, self.core.skill_index).detect()["candidates"]
            entities = [json.loads(r[0]) for r in conn.execute("SELECT payload FROM entities WHERE kind='candidate'")]
            result = []
            for candidate in detected:
                ids = sorted(candidate["evidence_jd_ids"])
                prior = [e for e in entities if e["anchor"] in ids]
                if len(prior) > 1:
                    raise ClosureError(409, "cluster merge requires manual reconciliation; prior versions retained")
                anchors = [key for key in ids if not by_id[key]["standard_job_title"] or by_id[key]["standardization_status"] == "仍需人工确认"]
                anchor = min(anchors or ids)
                entity = prior[0] if prior else self._entity("candidate", "CAND-"+fingerprint(anchor)[:12], anchor)
                evidence = [by_id[key] for key in ids]
                cfg = self.detector.config["evidence"]
                auto = definition(candidate["candidate_name"], evidence, self.core.skill_index, float(cfg["core_skill_min_ratio"]), int(cfg["maximum_core_skills"]))
                auto_hash = fingerprint([auto, evidence])
                latest = entity["versions"][-1] if entity["versions"] else None
                # Identical discovery cannot reset manual work or approval.
                if latest and latest["auto_fingerprint"] == auto_hash:
                    result.append(latest)
                    continue
                snapshot = dict(auto_definition=auto, manual_definition=None, evidence=evidence, auto_fingerprint=auto_hash,
                                discovery_score=candidate["emerging_score"], score_semantics="透明发现规则得分，不是岗位真实性概率",
                                company_count=candidate["company_count"], source_count=candidate["source_count"],
                                source_job_count=len(evidence), change_set=None)
                result.append(self._append(entity, snapshot, "candidate"))
                self._save(conn, entity)
            return result

    def _validate_manual(self, current, manual):
        fields = {"job_name", "core_responsibilities", "required_skills", "preferred_skills", "application_scenarios"}
        if not isinstance(manual, dict) or not fields <= manual.keys() or not isinstance(manual["job_name"], str) or not manual["job_name"].strip():
            raise ClosureError(422, "missing definition")
        evidence = {r["job_id"]: r for r in current["evidence"]}
        supported = {s["skill_id"]: s for s in skills_for(current["evidence"], self.core.skill_index)}
        clean = dict(job_name=manual["job_name"].strip(), job_name_supporting_job_ids=sorted(evidence))
        used = set()
        for field in ("required_skills", "preferred_skills"):
            if not isinstance(manual[field], list):
                raise ClosureError(422, "skills must be lists")
            clean[field] = []
            for item in manual[field]:
                key = item.get("skill_id") if isinstance(item, dict) else None
                if not isinstance(key, str) or key not in supported or key in used:
                    raise ClosureError(422, "manual skill lacks affirmed evidence or is duplicated")
                clean[field].append(supported[key])
                used.add(key)
        for field, sources in (("core_responsibilities", ["responsibilities"]), ("application_scenarios", ["industry", "scenario", "business_context"])):
            if not isinstance(manual[field], list):
                raise ClosureError(422, "definition text must be a list")
            clean[field] = []
            for item in manual[field]:
                if not isinstance(item, dict) or not isinstance(item.get("text"), str) or not item["text"].strip():
                    raise ClosureError(422, "invalid definition text")
                ids = item.get("supporting_job_ids")
                if not isinstance(ids, list) or not ids or any(not isinstance(key, str) or key not in evidence for key in ids):
                    raise ClosureError(422, "real supporting_job_ids required")
                snippets = [dict(job_id=key, source_field=source, text=evidence[key][source]) for key in sorted(set(ids)) for source in sources if evidence[key][source]]
                if any(not any(s["job_id"] == key for s in snippets) for key in ids):
                    raise ClosureError(422, "supporting JD has no evidence for this field")
                clean[field].append(dict(text=item["text"].strip(), supporting_job_ids=sorted(set(ids)), evidence_snippets=snippets, origin="manual_summary"))
        return clean

    def edit(self, kind, identifier, manual, expected_version, expected_revision):
        with self._db() as conn:
            entity = self._read(conn, kind, identifier)
            current = self._check(entity, expected_version, expected_revision)
            if kind != "candidate":
                raise ClosureError(400, "profile changes are evidence-derived; editing is candidate-only")
            if manual == (current["manual_definition"] or current["auto_definition"]):
                return current
            clean = self._validate_manual(current, manual)
            if clean == (current["manual_definition"] or current["auto_definition"]):
                return current
            snapshot = {k: v for k, v in current.items() if k not in {"kind", "id", "version", "previous_version", "revision", "status", "created_at", "fingerprint", "reviewed_at", "reviewer", "review_note"}}
            snapshot["manual_definition"] = clean
            result = self._append(entity, snapshot, "candidate")
            self._save(conn, entity)
            return result

    def action(self, kind, identifier, action, *, expected_version, expected_revision, reviewer=None, note="", acknowledge_gaps=False):
        transitions = {"submit": ({"candidate", "rejected"}, "pending_review"), "approve": ({"pending_review"}, "approved"),
                       "reject": ({"candidate", "pending_review", "approved"}, "rejected"), "publish": ({"approved"}, "published")}
        if action not in transitions:
            raise ClosureError(400, "invalid action")
        with self._db() as conn:
            entity = self._read(conn, kind, identifier)
            current = self._check(entity, expected_version, expected_revision)
            allowed, target = transitions[action]
            if current["status"] not in allowed:
                raise ClosureError(409, "invalid state transition")
            if action in {"approve", "reject"} and not note.strip():
                raise ClosureError(422, "review note required")
            if action == "approve":
                d = current["manual_definition"] or current["auto_definition"]
                if not d["job_name"] or not d["core_responsibilities"] or not d["required_skills"]:
                    raise ClosureError(422, "insufficient evidence: name, responsibilities and required skills required")
                if (not d["application_scenarios"] or not d["preferred_skills"]) and not acknowledge_gaps:
                    raise ClosureError(422, "explicit acknowledgement of insufficient fields required")
                if kind == "profile" and current["change_set"]["status"] != "ready":
                    raise ClosureError(422, "insufficient_sample or no_changes: no publishable update")
            current["status"] = target
            current["revision"] += 1
            if action in {"approve", "reject"}:
                current.update(reviewed_at=now(), reviewer=reviewer or None, review_note=note)
            entity["events"].append(dict(event=action, version=current["version"], revision=current["revision"], at=now(),
                                         reviewer=reviewer or None, note=note, acknowledge_gaps=acknowledge_gaps))
            if action == "publish":
                if kind == "profile" and current["base_profile_version"] != entity["publications"][-1]["profile_version"]:
                    raise ClosureError(409, "published baseline changed; recompute")
                publication = copy.deepcopy(current)
                publication.update(profile_version=len(entity["publications"])+1, published_at=now(), origin="human_approved")
                entity["publications"].append(publication)
            self._save(conn, entity)
            return current

    def diff(self, kind, identifier, before, after):
        entity = self.history(kind, identifier)
        try:
            if before < 1 or after < 1:
                raise IndexError
            old, new = entity["versions"][before-1], entity["versions"][after-1]
        except IndexError:
            raise ClosureError(404, "invalid version") from None
        return dict(definition_diff(old["manual_definition"] or old["auto_definition"], new["manual_definition"] or new["auto_definition"]),
                    before_version=before, after_version=after, evidence_count_before=len(old["evidence"]), evidence_count_after=len(new["evidence"]))

    def _profile_snapshot(self, title, rows):
        cfg = self.matching
        return dict(auto_definition=definition(title, rows, self.core.skill_index, float(cfg["minimum_required_frequency"]),
                        int(cfg["maximum_required_skills"]), float(cfg["minimum_bonus_frequency"]), int(cfg["maximum_bonus_skills"])),
                    manual_definition=None, evidence=rows, source_job_count=len(rows), observed_skills=skills_for(rows, self.core.skill_index),
                    window=rows[0]["time_value"] if rows else None, time_sources=sorted({r["time_source"] for r in rows}), change_set=None)

    @staticmethod
    def _latest_window(rows):
        valid = [r for r in rows if r["time_value"]]
        last = max((r["time_value"] for r in valid), default=None)
        return [r for r in valid if r["time_value"] == last]

    def run_update(self, title):
        with self._db() as conn:
            frozen = [r for r in self.base if r["standard_job_title"] == title]
            if not frozen:
                raise ClosureError(404, "existing job title not found")
            entity = self._read(conn, "profile", title) or self._entity("profile", title)
            if not entity["publications"]:
                baseline = self._profile_snapshot(title, self._latest_window(frozen))
                baseline.update(profile_version=1, origin="legacy_baseline", created_at=now())
                entity["publications"].append(baseline)
            before = entity["publications"][-1]
            relevant = [r for r in self._records(conn) if r["standard_job_title"] == title]
            after = self._profile_snapshot(title, self._latest_window(relevant))
            official_ids = {s["skill_id"] for field in ("required_skills", "preferred_skills") for s in before["auto_definition"][field]}
            withheld = [s for s in after["observed_skills"] if s["skill_id"] not in official_ids and s["evidence_count"] < int(self.evolution["new_skill_min_count"])]
            withheld_ids = {s["skill_id"] for s in withheld}
            for field in ("required_skills", "preferred_skills"):
                after["auto_definition"][field] = [s for s in after["auto_definition"][field] if s["skill_id"] not in withheld_ids]
            latest = entity["versions"][-1] if entity["versions"] else None
            new_hash = fingerprint(after["evidence"])
            if latest and fingerprint(latest["evidence"]) == new_hash and (latest["base_profile_version"] == before["profile_version"] or latest["status"] == "published"):
                return latest
            minimum = int(self.evolution["min_jd_count"])
            sufficient = len(before["evidence"]) >= minimum and len(after["evidence"]) >= minimum
            changes = dict(status="ready" if sufficient else "insufficient_sample", before_count=len(before["evidence"]),
                           after_count=len(after["evidence"]), minimum_sample=minimum, added_skills=[], removed_skills=[], modified_skills=[],
                           mode="snapshot_revision" if before["window"] == after["window"] else "daily_window_comparison",
                           before_window=before["window"], after_window=after["window"],
                           withheld_skills=withheld,
                           excluded_undated_job_ids=[r["job_id"] for r in relevant if not r["time_value"]],
                           notice="日窗口证据比较，不代表长期市场趋势；采集时间回退单独标注。")
            if sufficient and fingerprint(before["evidence"]) == new_hash:
                changes["status"] = "no_changes"
            if sufficient:
                old = {s["skill_id"]: s for s in before["observed_skills"]}
                new = {s["skill_id"]: s for s in after["observed_skills"]}
                def role(snapshot, key):
                    return next((f for f in ("required_skills", "preferred_skills") if any(s["skill_id"] == key for s in snapshot["auto_definition"][f])), "observed")
                for key in sorted(old.keys() | new.keys()):
                    a, b = old.get(key), new.get(key)
                    category = None
                    if a is None and b["evidence_count"] >= int(self.evolution["new_skill_min_count"]):
                        category = "added_skills"
                    elif b is None:
                        category = "removed_skills"
                    elif a and (a["coverage"] != b["coverage"] or role(before, key) != role(after, key)):
                        category = "modified_skills"
                    if category:
                        changes[category].append(dict(skill_id=key, skill_name=(b or a)["skill_name"], before=a["coverage"] if a else 0,
                            after=b["coverage"] if b else 0, before_role=role(before, key), after_role=role(after, key),
                            before_evidence=[r for r in before["evidence"] if a and r["job_id"] in a["supporting_job_ids"]],
                            after_evidence=[r for r in after["evidence"] if b and r["job_id"] in b["supporting_job_ids"]]))
            after.update(change_set=changes, base_profile_version=before["profile_version"])
            result = self._append(entity, after, "pending_review")
            self._save(conn, entity)
            return result
