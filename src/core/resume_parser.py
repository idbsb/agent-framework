from __future__ import annotations

import re

from ..schemas import ResumeParseRequest, ResumeParseResult
from .skill_extractor import SkillIndex


class ResumeParser:
    def __init__(self, skill_index: SkillIndex):
        self.skill_index = skill_index

    def parse(self, request: ResumeParseRequest | dict) -> ResumeParseResult:
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
        need_review = (not any(item.accepted for item in skills)
                       or any(item.need_human_review for item in skills)
                       or not request.education.strip() or not request.experience.strip())
        return ResumeParseResult(
            resume_id=request.resume_id,
            target_job=request.target_job,
            education=request.education,
            experience=request.experience,
            work_experience=request.work_experience,
            projects=projects,
            skills=skills,
            need_human_review=need_review,
        )

    def parse_row(self, row: dict) -> ResumeParseResult:
        return self.parse(ResumeParseRequest(
            resume_id=str(row.get("resume_id", "")),
            target_job=str(row.get("target_job", "")),
            education=str(row.get("education", "")),
            experience=str(row.get("experience", "")),
            work_experience=str(row.get("work_experience", "")),
            projects=str(row.get("projects", "")),
            skills_raw=str(row.get("skills_raw", "")),
        ))

