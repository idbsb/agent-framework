"""Deterministic, evidence-traceable job analysis built from the current JD corpus."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any


UNKNOWN = "招聘信息未明确"
MISSING_VALUES = {"", "无", "未提及", "未明确", "不详", "null", "none", "nan"}
PROJECT_TERMS = ("项目", "落地", "实践", "实战", "作品", "开源", "论文", "竞赛", "部署经验", "平台建设经验")


def _text(value: object) -> str:
    return str(value or "").strip()


def _has_content(value: object) -> bool:
    return _text(value).casefold() not in MISSING_VALUES


def _snippets(value: object) -> list[str]:
    if not _has_content(value):
        return []
    parts = re.split(r"[\r\n]+|(?<=[。！？；;])", _text(value))
    cleaned = []
    for part in parts:
        item = re.sub(r"^\s*(?:[-*●•]+|\d+[.、）)]|[（(]?\d+[）)])\s*", "", part).strip(" \t。；;")
        if len(item) >= 4:
            cleaned.append(item)
    return list(dict.fromkeys(cleaned))


class JobProfileBuilder:
    def __init__(self, rows: list[dict[str, Any]], skill_index, profile_config: dict[str, Any], aggregate_groups: dict[str, list[str]] | None = None):
        self.skill_index = skill_index
        self.profile_config = profile_config
        self.grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            title = _text(row.get("standard_job_title"))
            if title:
                self.grouped[title].append(row)
        rows_by_id = {_text(row.get("jd_id")): row for row in rows}
        for title, member_ids in (aggregate_groups or {}).items():
            combined = {str(row.get("jd_id")): row for row in self.grouped.get(title, [])}
            combined.update({jd_id: rows_by_id[jd_id] for jd_id in member_ids if jd_id in rows_by_id})
            self.grouped[title] = list(combined.values())

    @staticmethod
    def _summarize_values(rows: list[dict[str, Any]], *fields: str) -> tuple[str, int]:
        values = []
        for row in rows:
            value = next((_text(row.get(field)) for field in fields if _text(row.get(field))), "")
            if value.casefold() not in MISSING_VALUES:
                values.append(value)
        if not values:
            return UNKNOWN, 0
        counts = Counter(values)
        summary = "；".join(
            f"{value}（{count}/{len(rows)}条JD）" for value, count in counts.most_common(4)
        )
        return summary, len(values)

    @staticmethod
    def _ranked_snippets(rows: list[dict[str, Any]], fields: tuple[str, ...], predicate=None, limit: int = 10) -> list[str]:
        counts: Counter[str] = Counter()
        original: dict[str, str] = {}
        first_seen: dict[str, int] = {}
        sequence = 0
        for row in rows:
            seen_in_jd = set()
            for field in fields:
                for snippet in _snippets(row.get(field)):
                    if predicate and not predicate(snippet):
                        continue
                    key = re.sub(r"\s+", "", snippet).casefold()
                    original.setdefault(key, snippet)
                    first_seen.setdefault(key, sequence)
                    sequence += 1
                    seen_in_jd.add(key)
            counts.update(seen_in_jd)
        keys = sorted(counts, key=lambda key: (-counts[key], first_seen[key]))[:limit]
        return [original[key] for key in keys]

    def build(self, job_title: str, matching_profile: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = self.grouped.get(job_title, [])
        if not rows:
            return {"available": False, "job_title": job_title, "jd_count": 0, "message": "当前岗位尚无真实JD。"}
        total = len(rows)
        skill_evidence: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            extracted = self.skill_index.extract_fields([
                ("responsibilities", row.get("responsibilities")),
                ("required_skills_raw", row.get("required_skills_raw")),
                ("bonus_skills_raw", row.get("bonus_skills_raw")),
            ])
            for item in extracted:
                if item.accepted and item.polarity == "affirmed":
                    skill_evidence[item.skill_id].add(_text(row.get("jd_id")))
        frequencies = []
        for skill_id, evidence_ids in skill_evidence.items():
            ids = sorted(item for item in evidence_ids if item)
            count = len(ids)
            frequencies.append({
                "skill_id": skill_id,
                "skill_name": self.skill_index.standard_name(skill_id),
                "frequency": count / total,
                "evidence_jd_count": count,
                "sample_size": total,
                "evidence_jd_ids": ids,
            })
        frequencies.sort(key=lambda item: (-item["evidence_jd_count"], item["skill_name"]))

        profile = matching_profile or {}
        required_ids = profile.get("required_ids", [])
        bonus_ids = profile.get("bonus_ids", [])
        required = [self.skill_index.standard_name(skill_id) for skill_id in required_ids]
        bonus = [self.skill_index.standard_name(skill_id) for skill_id in bonus_ids]
        education, education_jd_count = self._summarize_values(rows, "education")
        experience, experience_jd_count = self._summarize_values(rows, "experience", "original_experience")
        responsibilities = self._ranked_snippets(rows, ("responsibilities",), limit=10)
        required_raw = self._ranked_snippets(rows, ("required_skills_raw",), limit=8)
        bonus_raw = self._ranked_snippets(rows, ("bonus_skills_raw",), limit=8)
        projects = self._ranked_snippets(
            rows,
            ("required_skills_raw", "bonus_skills_raw", "responsibilities"),
            predicate=lambda value: any(term in value for term in PROJECT_TERMS),
            limit=8,
        )
        return {
            "available": True,
            "job_title": job_title,
            "jd_count": total,
            "education": education,
            "education_jd_count": education_jd_count,
            "experience": experience,
            "experience_jd_count": experience_jd_count,
            "project_experience": "；".join(projects) if projects else UNKNOWN,
            "project_experience_jd_count": sum(
                any(any(term in snippet for term in PROJECT_TERMS) for field in ("required_skills_raw", "bonus_skills_raw", "responsibilities") for snippet in _snippets(row.get(field)))
                for row in rows
            ),
            "core_responsibilities": "；".join(responsibilities) if responsibilities else UNKNOWN,
            "responsibilities_jd_count": sum(_has_content(row.get("responsibilities")) for row in rows),
            "required_skills_text": "；".join(required or required_raw) if required or required_raw else UNKNOWN,
            "required_skills_jd_count": sum(_has_content(row.get("required_skills_raw")) for row in rows),
            "bonus_skills_text": "；".join(bonus or bonus_raw) if bonus or bonus_raw else UNKNOWN,
            "bonus_skills_jd_count": sum(_has_content(row.get("bonus_skills_raw")) for row in rows),
            "skill_frequencies": frequencies,
            "small_sample": total < 3,
            "sample_notice": "小样本提示：当前岗位招聘样本较少，暂不形成技能频率结论；以下仅展示JD提及证据。" if total < 3 else "",
            "message": "",
        }
