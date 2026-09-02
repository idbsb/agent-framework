import hashlib
import json
import re
from datetime import date
from urllib.parse import urlsplit


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def safe_url(value):
    if not value or re.search(r"[\x00-\x20\\]", value):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return None


def valid_date(value):
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (ValueError, TypeError):
        return None


def normalize_record(raw, index):
    fields = ("job_id", "original_title", "standard_job_title", "standardization_status", "company", "source", "url",
              "responsibilities", "required_skills_raw", "bonus_skills_raw", "industry", "scenario", "business_context", "technical_domain")
    row = {key: str(raw.get(key) or "").strip() for key in fields}
    for key in ("published_at", "collected_at", "first_seen_at"):
        row[key] = str(raw.get(key)) if valid_date(raw.get(key)) else None
    row["time_source"] = "published_at" if row["published_at"] else "collected_at_fallback" if row["collected_at"] else "unknown"
    row["time_value"] = valid_date(row["published_at"] or row["collected_at"])
    row["safe_url"] = safe_url(row["url"])
    row["skill_evidence"] = [s.model_dump() for s in index.extract_fields(
        (key, row[key]) for key in ("responsibilities", "required_skills_raw", "bonus_skills_raw"))]
    return row


def load_records(core):
    loader = core.loader
    source = loader.sources["standardized_jd_dataset"]
    extras = {str(r.get("JD编号")): r for r in loader.read_sheet(loader.resolve_path("standardized_jd_dataset"), source["sheet"])}
    result = []
    for raw in loader.load_jds():
        extra = extras.get(str(raw.get("jd_id")), {})
        row = dict(raw, job_id=raw.get("jd_id"), original_title=raw.get("original_job_title"), url=raw.get("source_url"),
                   published_at=extra.get("标准发布时间"), collected_at=extra.get("采集时间"))
        result.append(normalize_record(row, core.skill_index))
    return result


def skills_for(rows, index):
    support = {}
    for row in rows:
        for s in row["skill_evidence"]:
            if s["accepted"] and s["polarity"] == "affirmed":
                support.setdefault(s["skill_id"], {}).setdefault(row["job_id"], []).append(dict(
                    job_id=row["job_id"], source_field=s["source_field"], text=s["evidence"], start=s["start"], end=s["end"]))
    return [dict(skill_id=key, skill_name=index.standard_name(key), coverage=len(value)/len(rows),
                 evidence_count=len(value), supporting_job_ids=sorted(value),
                 evidence_snippets=[s for job in sorted(value) for s in value[job]])
            for key, value in sorted(support.items(), key=lambda p: (-len(p[1]), p[0]))]


def text_items(rows, fields):
    groups = {}
    for row in rows:
        for field in fields:
            for text in re.split(r"[\n；;。]+", row.get(field, "")):
                text = text.strip()
                if not text:
                    continue
                item = groups.setdefault(re.sub(r"\s+", " ", text), dict(text=text, supporting_job_ids=[], evidence_snippets=[]))
                if row["job_id"] not in item["supporting_job_ids"]:
                    item["supporting_job_ids"].append(row["job_id"])
                item["evidence_snippets"].append(dict(job_id=row["job_id"], source_field=field, text=row[field]))
    return sorted(groups.values(), key=lambda i: (-len(i["supporting_job_ids"]), i["text"]))


def definition(name, rows, index, required_ratio, maximum_required, preferred_ratio=None, maximum_preferred=10):
    skills = skills_for(rows, index)
    required = [s for s in skills if s["coverage"] >= required_ratio][:maximum_required]
    ids = {s["skill_id"] for s in required}
    # No existing emerging preferred threshold: explicitly require >=2 supporting JDs.
    preferred = [s for s in skills if s["skill_id"] not in ids and
                 (s["coverage"] >= preferred_ratio if preferred_ratio is not None else s["evidence_count"] >= 2)][:maximum_preferred]
    return dict(job_name=name, job_name_supporting_job_ids=[r["job_id"] for r in rows],
                core_responsibilities=text_items(rows, ["responsibilities"]), required_skills=required,
                preferred_skills=preferred, application_scenarios=text_items(rows, ["industry", "scenario", "business_context"]))


def definition_diff(before, after):
    def combined(d):
        return {s["skill_id"]: dict(s, role=f) for f in ("required_skills", "preferred_skills") for s in d[f]}
    old, new = combined(before), combined(after)
    return dict(added_skills=[new[k] for k in sorted(new.keys()-old.keys())],
                removed_skills=[old[k] for k in sorted(old.keys()-new.keys())],
                modified_skills=[dict(skill_id=k, before=old[k], after=new[k]) for k in sorted(old.keys() & new.keys()) if old[k] != new[k]],
                responsibilities_changed=before["core_responsibilities"] != after["core_responsibilities"],
                scenarios_changed=before["application_scenarios"] != after["application_scenarios"],
                job_name_changed=before["job_name"] != after["job_name"])
