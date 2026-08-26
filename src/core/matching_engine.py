from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import yaml

from ..data_loader import DataLoader
from ..schemas import MatchResult, ResumeParseResult
from .jd_parser import JDParser
from .skill_extractor import SkillIndex


def _years(text: str) -> float | None:
    matches = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*年", str(text or ""))]
    return max(matches) if matches else None


def _education_level(text: str) -> int | None:
    value = str(text or "")
    for label, level in (("博士", 4), ("硕士", 3), ("本科", 2), ("大专", 1), ("专科", 1)):
        if label in value:
            return level
    return None


class MatchingEngine:
    def __init__(self, loader: DataLoader, skill_index: SkillIndex, jd_parser: JDParser, config_path: str | Path | None = None):
        default = loader.project_root / "config" / "matching_weights.yaml"
        self.config_path = Path(config_path or default)
        self.config = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        self.weights = self.config["weights"]
        if abs(sum(float(value) for value in self.weights.values()) - 1.0) > 1e-9:
            raise ValueError("matching_weights.yaml 中权重之和必须为1")
        self.thresholds = self.config["thresholds"]
        self.profile_config = self.config["profile"]
        self.loader = loader
        self.skill_index = skill_index
        self.jd_parser = jd_parser
        self.profiles = self._build_profiles()

    def _build_profiles(self) -> dict[str, dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in self.loader.load_jds():
            title = str(row.get("standard_job_title", ""))
            if title:
                grouped[title].append(row)
        profiles = {}
        for title, rows in grouped.items():
            required, bonus = Counter(), Counter()
            education_levels, required_years = [], []
            for row in rows:
                required.update(item.skill_id for item in self.skill_index.extract_fields([
                    ("required_skills_raw", row.get("required_skills_raw"))
                ]))
                bonus.update(item.skill_id for item in self.skill_index.extract_fields([
                    ("bonus_skills_raw", row.get("bonus_skills_raw"))
                ]))
                level = _education_level(str(row.get("education", "")))
                years = _years(str(row.get("experience") or row.get("original_experience", "")))
                if level is not None:
                    education_levels.append(level)
                if years is not None:
                    required_years.append(years)
            required_min = max(1, math.ceil(len(rows) * float(self.profile_config["minimum_required_frequency"])))
            bonus_min = max(1, math.ceil(len(rows) * float(self.profile_config["minimum_bonus_frequency"])))
            req_ids = [skill_id for skill_id, count in required.most_common() if count >= required_min]
            bonus_ids = [skill_id for skill_id, count in bonus.most_common() if count >= bonus_min and skill_id not in req_ids]
            req_ids = req_ids[: int(self.profile_config["maximum_required_skills"])]
            bonus_ids = bonus_ids[: int(self.profile_config["maximum_bonus_skills"])]
            profiles[title] = {
                "jd_count": len(rows),
                "required_ids": req_ids,
                "bonus_ids": bonus_ids,
                "required_frequency": dict(required),
                "bonus_frequency": dict(bonus),
                "education_level": min(education_levels) if education_levels else None,
                "experience_years": min(required_years) if required_years else None,
            }
        return profiles

    @staticmethod
    def _ratio(intersection: int, denominator: int) -> float:
        return 100.0 if denominator == 0 else 100.0 * intersection / denominator

    def _learning_path(self, missing_names: list[str]) -> list[str]:
        recommendations = []
        for name in missing_names[:4]:
            if name == "MCP":
                action = "学习MCP基本协议、Client/Server交互和工具暴露"
            elif name == "MCP Server开发":
                action = "实现一个MCP Server并完成工具注册、调用和异常处理"
            elif name in {"LangGraph", "LangChain"}:
                action = f"学习{name}核心组件并完成一个可运行工作流"
            elif name in {"Docker", "Kubernetes"}:
                action = f"使用{name}完成目标项目的部署与复现实验"
            elif name in {"RAG", "Embedding", "向量数据库", "重排序"}:
                action = f"在RAG小项目中专项实现{name}并记录检索评测结果"
            else:
                action = f"学习{name}基础概念，完成一个可验证的小项目"
            recommendations.append(action)
        if missing_names:
            recommendations.append("完成综合项目后重新运行人岗匹配，比较各维度提升")
        else:
            recommendations.append("当前核心技能覆盖较好，可通过综合项目和部署实践继续巩固")
        return [f"{index}. {text}" for index, text in enumerate(recommendations, start=1)]

    def resolve_job_title(self, job_title: str) -> tuple[str, float]:
        if job_title in self.profiles:
            return job_title, 1.0
        best_title, best_score = "", 0.0
        compact = re.sub(r"[\s/（）()_-]+", "", job_title).casefold()
        for candidate in self.profiles:
            candidate_compact = re.sub(r"[\s/（）()_-]+", "", candidate).casefold()
            score = SequenceMatcher(None, compact, candidate_compact).ratio()
            if score > best_score:
                best_title, best_score = candidate, score
        return (best_title, best_score) if best_score >= 0.65 else (job_title, best_score)

    def match(self, resume: ResumeParseResult, job_title: str) -> MatchResult:
        resolved_title, title_confidence = self.resolve_job_title(job_title)
        profile = self.profiles.get(resolved_title)
        if profile is None:
            return MatchResult(
                resume_id=resume.resume_id, job_title=job_title, match_score=0,
                dimension_scores={key: 0 for key in self.weights},
                recommendations=["目标岗位尚无可用正式JD画像，请先人工确认岗位名称。"],
                explanation=["未找到目标岗位的正式JD聚合画像。"], need_human_review=True,
            )
        resume_ids = {item.skill_id for item in resume.skills if item.accepted}
        required_ids, bonus_ids = set(profile["required_ids"]), set(profile["bonus_ids"])
        matched_required = required_ids & resume_ids
        matched_bonus = bonus_ids & resume_ids
        project_ids = {item.skill_id for item in resume.skills if item.source_field == "projects" and item.accepted}
        project_denominator = min(3, len(required_ids))
        dimension_scores = {
            "required_skills": self._ratio(len(matched_required), len(required_ids)),
            "bonus_skills": self._ratio(len(matched_bonus), len(bonus_ids)),
            "projects": self._ratio(len(project_ids & required_ids), project_denominator),
            "experience": 100.0,
            "education": 100.0,
        }
        resume_years = _years(resume.experience + " " + resume.work_experience)
        required_years = profile["experience_years"]
        if required_years is not None:
            dimension_scores["experience"] = 50.0 if resume_years is None else min(100.0, 100.0 * resume_years / max(required_years, 0.5))
        resume_education = _education_level(resume.education)
        required_education = profile["education_level"]
        if required_education is not None:
            dimension_scores["education"] = 50.0 if resume_education is None else min(100.0, 100.0 * resume_education / required_education)
        score = sum(dimension_scores[key] * float(weight) for key, weight in self.weights.items())
        missing_ids = sorted(required_ids - resume_ids, key=lambda sid: (-profile["required_frequency"].get(sid, 0), self.skill_index.standard_name(sid)))
        matched_ids = sorted((required_ids | bonus_ids) & resume_ids, key=self.skill_index.standard_name)
        advantage_ids = sorted(resume_ids - required_ids, key=self.skill_index.standard_name)
        missing_names = [self.skill_index.standard_name(skill_id) for skill_id in missing_ids]
        matched_names = [self.skill_index.standard_name(skill_id) for skill_id in matched_ids]
        advantage_names = [self.skill_index.standard_name(skill_id) for skill_id in advantage_ids]
        explanation = [
            f"目标岗位解析：{job_title} → {resolved_title}（置信度{title_confidence:.2f}）",
            f"必备技能：{len(matched_required)}/{len(required_ids)}",
            f"加分技能：{len(matched_bonus)}/{len(bonus_ids)}",
            f"项目中出现的必备技能：{len(project_ids & required_ids)}",
            f"经验要求基准：{required_years if required_years is not None else '未明确'}年；简历解析：{resume_years if resume_years is not None else '未识别'}年",
            f"学历要求等级：{required_education if required_education is not None else '未明确'}；简历学历等级：{resume_education if resume_education is not None else '未识别'}",
        ]
        return MatchResult(
            resume_id=resume.resume_id,
            job_title=resolved_title,
            match_score=round(score, 2),
            dimension_scores={key: round(value, 2) for key, value in dimension_scores.items()},
            matched_skills=matched_names,
            missing_skills=missing_names,
            advantage_skills=advantage_names,
            priority_skills=missing_names[:5],
            recommendations=self._learning_path(missing_names),
            explanation=explanation,
            need_human_review=resume.need_human_review or not required_ids,
        )

    def level_for_score(self, score: float) -> str:
        if score >= float(self.thresholds["high"]):
            return "高"
        if score >= float(self.thresholds["medium"]):
            return "中"
        return "低"
