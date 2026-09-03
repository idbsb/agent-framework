from __future__ import annotations

import re

from ..schemas import ResumeParseRequest, ResumeParseResult
from .skill_extractor import SkillIndex


class ResumeParser:
    def __init__(self, skill_index: SkillIndex):
        self.skill_index = skill_index

    def parse(self, request: ResumeParseRequest | dict, job_requirements: dict | None = None) -> ResumeParseResult:
        if not isinstance(request, ResumeParseRequest):
            request = ResumeParseRequest.model_validate(request)
        skills = self.skill_index.extract_fields([
            ("skills_raw", request.skills_raw),
            ("projects", request.projects),
            ("work_experience", request.work_experience),
        ])
        projects = [part.strip() for part in re.split(r"\n\s*\n|；(?=\S)", request.projects) if part.strip()]
        if not projects and request.projects.strip() and request.projects.strip() != "无":
            projects = [request.projects.strip()]
        # Conflicting claims are preserved, but cannot silently grant credit.
        states: dict[str, set[str]] = {}
        for item in skills:
            states.setdefault(item.skill_id, set()).add(item.polarity)
        for item in skills:
            if "affirmed" in states[item.skill_id] and "negated" in states[item.skill_id]:
                item.accepted = False
                item.need_human_review = True
        reliable_ids = {item.skill_id for item in skills if item.accepted and item.evidence_strength in {"strong", "medium"}}
        weak_ids = {item.skill_id for item in skills if item.evidence_strength == "weak"}
        profile = job_requirements or {}
        core_ids = [skill_id for skill_id in profile.get("required_ids", []) if skill_id in self.skill_index.skills]
        bonus_ids = [skill_id for skill_id in profile.get("bonus_ids", []) if skill_id in self.skill_index.skills]
        requirement_ids = list(dict.fromkeys([*core_ids, *bonus_ids]))

        def names(ids: list[str] | set[str]) -> list[str]:
            return [self.skill_index.standard_name(skill_id) for skill_id in ids if skill_id in self.skill_index.skills]

        core_covered = [skill_id for skill_id in core_ids if skill_id in reliable_ids]
        bonus_covered = [skill_id for skill_id in bonus_ids if skill_id in reliable_ids]
        weak_required = list(dict.fromkeys(
            item.skill_id for item in skills
            if item.skill_id in weak_ids and item.skill_id not in reliable_ids
        ))
        missing = [skill_id for skill_id in requirement_ids if skill_id not in reliable_ids]
        numerator = len(set(requirement_ids) & reliable_ids)
        denominator = len(requirement_ids)
        need_review = (not any(item.accepted for item in skills)
                       or any(item.need_human_review for item in skills)
                       or not request.education.strip() or not request.experience.strip())
        return ResumeParseResult(
            resume_id=request.resume_id,
            name=request.name,
            phone=request.phone,
            email=request.email,
            target_job=request.target_job,
            target_job_source=(request.target_job_source if request.target_job_source != "unknown"
                               else ("user_input" if request.target_job.strip() else "unknown")),
            education=request.education,
            degree=request.degree,
            major=request.major,
            experience=request.experience,
            experience_source=(request.experience_source if request.experience_source != "unknown"
                               else ("user_input" if request.experience.strip() else "unknown")),
            work_experience=request.work_experience,
            projects=projects,
            skills=skills,
            core_skills_covered=names(core_covered),
            bonus_skills_covered=names(bonus_covered),
            weak_evidence_skills=names(weak_required),
            missing_skills=names(missing),
            coverage_numerator=numerator,
            coverage_denominator=denominator,
            coverage_rate=(numerator / denominator if denominator else None),
            need_human_review=need_review,
        )

    def parse_row(self, row: dict) -> ResumeParseResult:
        return self.parse(ResumeParseRequest(
            resume_id=str(row.get("resume_id", "")),
            name=str(row.get("name", "")),
            phone=str(row.get("phone", "")),
            email=str(row.get("email", "")),
            target_job=str(row.get("target_job", "")),
            target_job_source="user_input" if str(row.get("target_job", "")).strip() else "unknown",
            education=str(row.get("education", "")),
            degree=str(row.get("degree", "")),
            major=str(row.get("major", "")),
            experience=str(row.get("experience", "")),
            work_experience=str(row.get("work_experience", "")),
            projects=str(row.get("projects", "")),
            skills_raw=str(row.get("skills_raw", "")),
        ))

