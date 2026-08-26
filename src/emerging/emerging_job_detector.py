from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from ..core.skill_extractor import SkillIndex
from ..data_loader import DataLoader
from .cluster_analyzer import ClusterAnalyzer, JobVector
from .evidence_validator import validate_candidates


def _text(value: object) -> str:
    return str(value or "").strip()


def _ratio(value: int, target: int) -> float:
    return min(1.0, value / max(1, target))


class EmergingJobDetector:
    """Find candidates from real JD evidence; never creates occupations with an LLM."""

    def __init__(
        self,
        loader: DataLoader,
        skill_index: SkillIndex,
        config_path: str | Path | None = None,
    ):
        self.loader = loader
        self.skill_index = skill_index
        default = loader.project_root / "config" / "emerging_job_config.yaml"
        self.config_path = Path(config_path or default)
        self.config = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        weights = self.config["weights"]
        if abs(sum(float(value) for value in weights.values()) - 1.0) > 1e-9:
            raise ValueError("emerging_job_config.yaml 中权重之和必须为1")
        self.clusterer = ClusterAnalyzer(self.config)

    def _published_dates(self) -> dict[str, date | None]:
        source = self.loader.sources["standardized_jd_dataset"]
        rows = self.loader.read_sheet(self.loader.resolve_path("standardized_jd_dataset"), source["sheet"])
        result: dict[str, date | None] = {}
        for row in rows:
            value = row.get("标准发布时间")
            parsed: date | None = None
            if isinstance(value, str) and value:
                try:
                    parsed = date.fromisoformat(value[:10])
                except ValueError:
                    parsed = None
            result[_text(row.get("JD编号"))] = parsed
        return result

    def _records(self) -> list[dict[str, Any]]:
        published = self._published_dates()
        result = []
        for row in self.loader.load_jds():
            skills = self.skill_index.extract_fields([
                ("responsibilities", row.get("responsibilities")),
                ("required_skills_raw", row.get("required_skills_raw")),
                ("bonus_skills_raw", row.get("bonus_skills_raw")),
            ])
            item = dict(row)
            item["skill_evidence"] = [skill.model_dump() for skill in skills if skill.accepted]
            item["skill_ids"] = {skill.skill_id for skill in skills if skill.accepted}
            item["published_date"] = published.get(_text(row.get("jd_id")))
            result.append(item)
        return result

    @staticmethod
    def _vectors(records: list[dict[str, Any]]) -> list[JobVector]:
        return [
            JobVector(
                jd_id=_text(row.get("jd_id")),
                title=_text(row.get("original_job_title")),
                skill_ids=frozenset(row.get("skill_ids", set())),
            )
            for row in records
        ]

    def _profiles(self, records: list[dict[str, Any]]) -> dict[str, set[str]]:
        groups: dict[str, Counter[str]] = defaultdict(Counter)
        counts: Counter[str] = Counter()
        for row in records:
            title = _text(row.get("standard_job_title"))
            if not title or _text(row.get("standardization_status")) == "仍需人工确认":
                continue
            counts[title] += 1
            groups[title].update(row.get("skill_ids", set()))
        profiles = {}
        for title, frequencies in groups.items():
            minimum = max(1, math.ceil(counts[title] * 0.25))
            profiles[title] = {skill_id for skill_id, count in frequencies.items() if count >= minimum}
        return profiles

    def _closest_profile(self, skill_ids: set[str], profiles: dict[str, set[str]]) -> tuple[str, float]:
        best_title, best_score = "", 0.0
        for title, profile in profiles.items():
            union = skill_ids | profile
            score = len(skill_ids & profile) / len(union) if union else 0.0
            if score > best_score:
                best_title, best_score = title, score
        return best_title, best_score

    def _representative_title(self, rows: list[dict[str, Any]], vectors: dict[str, JobVector]) -> str:
        title_counts = Counter(_text(row.get("original_job_title")) for row in rows)
        top_count = max(title_counts.values())
        choices = sorted(title for title, count in title_counts.items() if count == top_count)
        if len(choices) == 1:
            return choices[0]
        centrality = {}
        for title in choices:
            title_rows = [row for row in rows if _text(row.get("original_job_title")) == title]
            representative = vectors[_text(title_rows[0].get("jd_id"))]
            centrality[title] = sum(self.clusterer.similarity(representative, vectors[_text(row.get("jd_id"))]) for row in rows)
        return max(choices, key=lambda value: (centrality[value], value))

    def _candidate(self, rows: list[dict[str, Any]], all_vectors: dict[str, JobVector], profiles: dict[str, set[str]], max_date: date | None) -> dict[str, Any]:
        vectors = [all_vectors[_text(row.get("jd_id"))] for row in rows]
        skill_counts: Counter[str] = Counter()
        title_values = [_text(row.get("original_job_title")) for row in rows]
        for row in rows:
            skill_counts.update(row.get("skill_ids", set()))
        minimum = max(1, math.ceil(len(rows) * float(self.config["evidence"]["core_skill_min_ratio"])))
        core_ids = [skill_id for skill_id, count in skill_counts.most_common() if count >= minimum]
        core_ids = core_ids[: int(self.config["evidence"]["maximum_core_skills"])]
        closest_title, closest_similarity = self._closest_profile(set(core_ids), profiles)
        closest_ids = profiles.get(closest_title, set())
        distinguishing_ids = [skill_id for skill_id in core_ids if skill_id not in closest_ids]
        distinguishing_ids = distinguishing_ids[: int(self.config["evidence"]["maximum_distinguishing_skills"])]

        known_titles = list(profiles)
        title_novelty_values = []
        for row in rows:
            if not _text(row.get("standard_job_title")):
                title_novelty_values.append(1.0)
                continue
            similarity = max((self.clusterer.title_similarity(_text(row.get("original_job_title")), title) for title in known_titles), default=0.0)
            title_novelty_values.append(1.0 - similarity)
        title_novelty = sum(title_novelty_values) / len(title_novelty_values)
        skill_novelty = 1.0 - closest_similarity
        consistency = self.clusterer.consistency(vectors)
        sources = sorted({_text(row.get("source")) for row in rows if _text(row.get("source"))})
        companies = sorted({_text(row.get("company")) for row in rows if _text(row.get("company"))})
        dates = [row.get("published_date") for row in rows if row.get("published_date")]
        recent_days = int(self.config["recency"]["recent_days"])
        recent_signal = 0.0
        if max_date and dates:
            cutoff = max_date - timedelta(days=recent_days)
            recent_signal = sum(1 for value in dates if value >= cutoff) / len(rows)

        signals = {
            "title_novelty": title_novelty,
            "skill_novelty": skill_novelty,
            "cluster_consistency": consistency,
            "evidence_count": _ratio(len(rows), int(self.config["evidence"]["target_jd_count"])),
            "source_diversity": _ratio(len(sources), int(self.config["evidence"]["target_source_count"])),
            "company_diversity": _ratio(len(companies), int(self.config["evidence"]["target_company_count"])),
            "recent_signal": recent_signal,
        }
        score = 100.0 * sum(float(self.config["weights"][key]) * value for key, value in signals.items())
        if len(rows) <= 1:
            score = min(score, float(self.config["thresholds"]["singleton_score_cap"]))
        score = round(score, 2)
        if len(rows) > 1 and score >= float(self.config["thresholds"]["high_confidence"]):
            confidence = "高置信候选"
        elif len(rows) > 1 and score >= float(self.config["thresholds"]["medium_confidence"]):
            confidence = "中置信候选"
        else:
            confidence = "弱候选/待观察"

        evidence_records = []
        for row in sorted(rows, key=lambda value: _text(value.get("jd_id"))):
            evidence_records.append({
                "jd_id": _text(row.get("jd_id")),
                "original_job_title": _text(row.get("original_job_title")),
                "standard_job_title": _text(row.get("standard_job_title")),
                "standardization_status": _text(row.get("standardization_status")),
                "company": _text(row.get("company")),
                "source": _text(row.get("source")),
                "source_url": _text(row.get("source_url")),
                "published_date": row.get("published_date").isoformat() if row.get("published_date") else "",
                "responsibilities": _text(row.get("responsibilities")),
                "required_skills_raw": _text(row.get("required_skills_raw")),
                "bonus_skills_raw": _text(row.get("bonus_skills_raw")),
                "skill_evidence": row.get("skill_evidence", []),
            })
        representative_evidence = [
            {
                "jd_id": item["jd_id"],
                "title": item["original_job_title"],
                "company": item["company"],
                "source": item["source"],
                "evidence": item["required_skills_raw"] or item["responsibilities"],
            }
            for item in evidence_records[:3]
        ]
        candidate_name = self._representative_title(rows, all_vectors)
        skill_names = [self.skill_index.standard_name(skill_id) for skill_id in core_ids]
        distinguishing_names = [self.skill_index.standard_name(skill_id) for skill_id in distinguishing_ids]
        relation = f"最接近现有岗位“{closest_title}”（核心技能Jaccard相似度 {closest_similarity:.2f}）" if closest_title else "未找到可比较的现有岗位画像"
        why = (
            f"标题新颖性 {title_novelty:.2f}，技能新颖性 {skill_novelty:.2f}，"
            f"簇一致性 {consistency:.2f}；共 {len(rows)} 条真实JD、{len(companies)} 家企业、{len(sources)} 个招聘来源。"
        )
        return {
            "candidate_id": "",
            "candidate_name": candidate_name,
            "emerging_score": score,
            "confidence_level": confidence,
            "representative_titles": sorted(set(title_values)),
            "core_skills": skill_names,
            "distinguishing_skills": distinguishing_names,
            "jd_count": len(rows),
            "evidence_count": len(evidence_records),
            "evidence_jd_ids": [item["jd_id"] for item in evidence_records],
            "representative_evidence": representative_evidence,
            "evidence_records": evidence_records,
            "source_count": len(sources),
            "sources": sources,
            "company_count": len(companies),
            "companies": companies,
            "why_emerging": why,
            "relation_to_existing_jobs": relation,
            "need_human_review": True,
            "signals": {key: round(value, 4) for key, value in signals.items()},
        }

    def detect(self) -> dict[str, Any]:
        records = self._records()
        by_id = {_text(row.get("jd_id")): row for row in records}
        vectors = self._vectors(records)
        vector_by_id = {item.jd_id: item for item in vectors}
        seed_records = [
            row for row in records
            if not _text(row.get("standard_job_title")) or _text(row.get("standardization_status")) == "仍需人工确认"
        ]
        seed_ids = {_text(row.get("jd_id")) for row in seed_records}
        seed_vectors = [vector_by_id[value] for value in sorted(seed_ids)]
        support_vectors = [item for item in vectors if item.jd_id not in seed_ids]
        components = self.clusterer.components(seed_vectors, support_vectors)
        profiles = self._profiles(records)
        dates = [row.get("published_date") for row in records if row.get("published_date")]
        max_date = max(dates) if dates else None
        candidates = [self._candidate([by_id[jd_id] for jd_id in ids], vector_by_id, profiles, max_date) for ids in components]
        candidates.sort(key=lambda item: (-item["emerging_score"], -item["jd_count"], item["candidate_name"]))
        for index, item in enumerate(candidates, start=1):
            item["candidate_id"] = f"EMERGING-{index:03d}"
        validation = validate_candidates(candidates, set(by_id))
        if not validation["passed"]:
            raise ValueError(f"新岗位 Evidence 校验失败：{validation['errors']}")
        level_counts = Counter(item["confidence_level"] for item in candidates)
        generated_at = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
        return {
            "schema_version": "1.0",
            "data_version": self.loader.version.get("data_version"),
            "generated_at": generated_at,
            "source_jd_count": len(records),
            "observation_seed_count": len(seed_records),
            "methodology": "真实岗位标题字符特征 + 标准技能集合相似度 + 确定性聚类 + 多源Evidence透明评分",
            "notice": "结果为新岗位候选观察，不等同于国家正式职业分类中的新职业。",
            "summary": {
                "candidate_count": len(candidates),
                "high_confidence": level_counts.get("高置信候选", 0),
                "medium_confidence": level_counts.get("中置信候选", 0),
                "weak_candidate": level_counts.get("弱候选/待观察", 0),
            },
            "validation": validation,
            "candidates": candidates,
        }

