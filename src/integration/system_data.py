from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from ..api.service import CoreServices
from .evolution_adapter import EvolutionAdapter
from .graph_adapter import GraphAdapter


def _text(value: object) -> str:
    return str(value or "").strip()


class SystemDataService:
    def __init__(self, services: CoreServices):
        self.services = services
        self.loader = services.loader
        self.project_root = self.loader.project_root
        self.graph = GraphAdapter(self.loader, services.skill_index, effective_profiles=services.matching_engine.effective_profiles)
        self.evolution = EvolutionAdapter(self.project_root)

    def _emerging(self) -> dict[str, Any]:
        errors: list[str] = []
        for filename, status in (("emerging_jobs_v2.json", "generated_v2"), ("emerging_jobs_v1.json", "fallback_v1")):
            path = self.project_root / "outputs" / filename
            if not path.exists():
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(value.get("candidates"), list) or not isinstance(value.get("summary"), dict):
                    raise ValueError("候选或摘要结构无效")
                if filename.endswith("v2.json") and not value.get("validation", {}).get("passed"):
                    raise ValueError("V2数据校验未通过")
                value["available"] = True
                value["status"] = status
                value["loaded_from"] = filename
                if errors:
                    value["fallback_reason"] = "；".join(errors)
                return value
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                errors.append(f"{filename}: {exc}")
        return {"available": False, "status": "not_generated", "message": "当前模块数据尚未生成。", "summary": {}, "candidates": [], "load_errors": errors}

    def emerging_list(self) -> dict[str, Any]:
        return self._emerging()

    def emerging_detail(self, candidate_id: str) -> dict[str, Any] | None:
        return next((item for item in self._emerging().get("candidates", []) if item.get("candidate_id") == candidate_id), None)

    def overview(self) -> dict[str, Any]:
        rows = self.loader.load_jds()
        resumes = self.loader.load_resumes()
        skills, _ = self.loader.load_skill_dictionary()
        graph = self.graph.load()
        emerging = self._emerging()
        job_counts = Counter(_text(row.get("standard_job_title")) for row in rows if _text(row.get("standard_job_title")))
        source_counts = Counter(_text(row.get("source")) for row in rows if _text(row.get("source")))
        skill_counts: Counter[str] = Counter()
        evidence_covered = 0
        for row in rows:
            extracted = self.services.skill_index.extract_fields([
                ("responsibilities", row.get("responsibilities")),
                ("required_skills_raw", row.get("required_skills_raw")),
                ("bonus_skills_raw", row.get("bonus_skills_raw")),
            ])
            if any(item.accepted for item in extracted):
                evidence_covered += 1
            # A JD contributes at most once per skill, even with many evidence spans.
            skill_counts.update({item.standard_skill_name for item in extracted if item.accepted})
        return {
            "data_version": self.loader.version.get("data_version"),
            "truth_statement": f"当前系统基于{len(rows)}条真实招聘JD构建。",
            "metrics": {
                "jd_count": len(rows),
                "standard_job_count": len(job_counts),
                "standard_skill_count": len(self.services.skill_index.skills),
                "frozen_standard_skill_count": len(skills),
                "graph_node_count": graph.get("summary", {}).get("node_count", 0),
                "graph_edge_count": graph.get("summary", {}).get("edge_count", 0),
                "resume_count": len(resumes),
                "evidence_covered_jd_count": evidence_covered,
            },
            "top_jobs": [{"job_title": title, "jd_count": count} for title, count in job_counts.most_common(8)],
            "top_skills": [{"skill_name": name, "evidence_jd_count": count} for name, count in skill_counts.most_common(10)],
            "sources": [{"source": name, "jd_count": count} for name, count in source_counts.most_common()],
            "graph_status": {key: graph.get(key) for key in ["available", "status", "source_label", "notice"]},
            "evolution_status": self.evolution.for_job("AI Agent开发工程师"),
            "emerging_summary": emerging.get("summary", {}),
            "emerging_candidates": emerging.get("candidates", [])[:3],
        }

    def job_analysis(self, job_title: str) -> dict[str, Any]:
        reader = self.services.matching_engine.effective_profiles
        effective = reader.get_effective_job_profile(job_title)
        profile_path = self.project_root / "outputs" / "job_profiles_cleaned.xlsx"
        profile = None
        if profile_path.exists():
            rows = self.loader.read_sheet(profile_path, "岗位能力画像")
            profile = next((row for row in rows if _text(row.get("岗位名称")) == job_title), None)
        matching_profile = effective["matching_profile"] or {}
        graph = self.graph.for_job(job_title, limit=30, effective_profile=effective)
        skills_by_id = {node.get("id"): node.get("name") for node in graph.get("nodes", []) if node.get("type") == "skill"}
        frequencies = [
            {
                "skill_id": edge.get("target"),
                "skill_name": skills_by_id.get(edge.get("target"), str(edge.get("target", ""))),
                "frequency": edge.get("frequency", 0),
                "importance": edge.get("importance", ""),
                "skill_level": edge.get("skill_level", ""),
                "evidence_jd_ids": edge.get("evidence_jd_ids", []),
            }
            for edge in graph.get("edges", [])
        ]
        result = {
            "available": bool(profile or matching_profile),
            "job_title": job_title,
            "jd_count": int((profile or {}).get("JD数量") or matching_profile.get("jd_count") or 0),
            "core_responsibilities": _text((profile or {}).get("核心职责")),
            "required_skills_text": _text((profile or {}).get("必备技能")),
            "bonus_skills_text": _text((profile or {}).get("加分技能")),
            "project_experience": _text((profile or {}).get("项目经历")),
            "education": _text((profile or {}).get("学历要求")),
            "experience": _text((profile or {}).get("经验要求")),
            "skill_frequencies": frequencies,
            "graph_source_label": graph.get("source_label", ""),
            "message": "" if profile or matching_profile else "当前岗位尚无正式能力画像。",
        }
        result.update(reader.metadata(effective))
        if effective["profile_source"] == "published_dynamic":
            d = effective["definition"]
            result.update(available=True, jd_count=matching_profile["jd_count"],
                          core_responsibilities="；".join(r["text"] for r in d["core_responsibilities"]),
                          required_skills_text="；".join(s["skill_name"] for s in d["required_skills"]),
                          bonus_skills_text="；".join(s["skill_name"] for s in d["preferred_skills"]),
                          published_profile=effective["publication"])
        return result
