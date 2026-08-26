from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher

from ..data_loader import DataLoader
from ..schemas import JDParseRequest, JDParseResult
from .skill_extractor import SkillIndex, normalize


def _title_key(value: object) -> str:
    text = normalize(value)
    return re.sub(r"[\s()（）\-_/·—]+", "", text)


class JDParser:
    def __init__(self, loader: DataLoader, skill_index: SkillIndex, review_threshold: float = 0.65):
        self.loader = loader
        self.skill_index = skill_index
        self.review_threshold = review_threshold
        self.mapping_rows = loader.load_job_title_mapping()
        self.by_jd_id = {str(row["jd_id"]): row for row in self.mapping_rows}
        self.by_original: dict[str, dict] = {}
        self.standard_titles = sorted({str(row["standard_job_title"]) for row in self.mapping_rows if row["standard_job_title"]})
        for row in self.mapping_rows:
            if row["standard_job_title"] and row["status"] != "仍需人工确认":
                self.by_original.setdefault(_title_key(row["original_job_title"]), row)
                self.by_original.setdefault(_title_key(row["cleaned_job_title"]), row)

        profiles: dict[str, list[set[str]]] = defaultdict(list)
        for row in loader.load_jds():
            title = str(row.get("standard_job_title", ""))
            if not title or row.get("standardization_status") == "仍需人工确认":
                continue
            skills = self.skill_index.extract_fields([
                ("required_skills_raw", row.get("required_skills_raw")),
                ("bonus_skills_raw", row.get("bonus_skills_raw")),
                ("responsibilities", row.get("responsibilities")),
            ])
            profiles[title].append({item.skill_id for item in skills if item.accepted})
        self.title_skill_profiles = {
            title: set().union(*groups) if groups else set() for title, groups in profiles.items()
        }

    def _predict_title(self, request: JDParseRequest, parsed_skill_ids: set[str]) -> tuple[str, float, bool, str]:
        mapping = self.by_jd_id.get(request.jd_id)
        if mapping and mapping.get("standard_job_title") and mapping.get("status") != "仍需人工确认":
            confidence = 0.96 if mapping.get("status") == "根据JD正文确认" else 0.99
            return str(mapping["standard_job_title"]), confidence, False, f"正式岗位映射：{mapping.get('status')}"

        exact = self.by_original.get(_title_key(request.original_job_title))
        if exact:
            return str(exact["standard_job_title"]), 0.96, False, "原始岗位名称命中正式映射"

        best_title, best_score = "", 0.0
        original_key = _title_key(request.original_job_title)
        for title in self.standard_titles:
            title_score = SequenceMatcher(None, original_key, _title_key(title)).ratio()
            profile = self.title_skill_profiles.get(title, set())
            union = parsed_skill_ids | profile
            skill_score = len(parsed_skill_ids & profile) / len(union) if union else 0.0
            score = 0.72 * title_score + 0.28 * skill_score
            if score > best_score:
                best_title, best_score = title, score
        confidence = round(min(0.89, best_score), 4)
        needs_review = confidence < self.review_threshold or bool(mapping and mapping.get("status") == "仍需人工确认")
        reason = "标题相似度与JD技能画像联合预测；无正式真值" if mapping else "新增JD标题相似度与技能画像联合预测"
        return best_title, confidence, needs_review, reason

    def parse(self, request: JDParseRequest | dict) -> JDParseResult:
        if not isinstance(request, JDParseRequest):
            request = JDParseRequest.model_validate(request)
        skills = self.skill_index.extract_fields([
            ("required_skills_raw", request.required_skills_raw),
            ("bonus_skills_raw", request.bonus_skills_raw),
            ("responsibilities", request.responsibilities),
        ])
        parsed_skill_ids = {item.skill_id for item in skills if item.accepted}
        title, confidence, title_review, title_reason = self._predict_title(request, parsed_skill_ids)
        need_review = title_review or any(not item.accepted for item in skills) or not title
        return JDParseResult(
            jd_id=request.jd_id,
            job_title=title,
            original_job_title=request.original_job_title,
            predicted_standard_job_title=title,
            job_confidence=confidence,
            responsibilities=request.responsibilities,
            education=request.education,
            experience=request.experience,
            skills=skills,
            evidence=[title_reason],
            need_human_review=need_review,
        )

    def parse_row(self, row: dict) -> JDParseResult:
        return self.parse(JDParseRequest(
            jd_id=str(row.get("jd_id", "")),
            original_job_title=str(row.get("original_job_title", "")),
            responsibilities=str(row.get("responsibilities", "")),
            required_skills_raw=str(row.get("required_skills_raw", "")),
            bonus_skills_raw=str(row.get("bonus_skills_raw", "")),
            education=str(row.get("education", "")),
            experience=str(row.get("experience") or row.get("original_experience", "")),
        ))

