from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StableModel(BaseModel):
    """Public schema base. Field names are the stable integration contract."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SkillEvidence(StableModel):
    # Evidence and offsets refer to the unmodified source field, including spaces.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    skill_id: str
    standard_skill_name: str
    skill_type: str = "未分类"
    confidence: float = Field(ge=0, le=1)
    evidence: str
    source_field: str
    accepted: bool = True
    polarity: Literal["affirmed", "negated", "planned", "other_person", "uncertain"] = "affirmed"
    matched_text: str = ""
    start: int | None = None
    end: int | None = None
    need_human_review: bool = False
    confidence_semantics: str = "rule_match_strength_not_mastery_probability"


class JDParseRequest(StableModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    jd_id: str = "JD-INPUT"
    original_job_title: str
    responsibilities: str = ""
    required_skills_raw: str = ""
    bonus_skills_raw: str = ""
    education: str = ""
    experience: str = ""


class JDParseResult(StableModel):
    jd_id: str
    job_title: str
    original_job_title: str
    predicted_standard_job_title: str = ""
    job_confidence: float = Field(ge=0, le=1)
    responsibilities: str = ""
    education: str = ""
    experience: str = ""
    skills: list[SkillEvidence] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    need_human_review: bool = False


class ResumeParseRequest(StableModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    resume_id: str = "RESUME-INPUT"
    target_job: str = ""
    education: str = ""
    experience: str = ""
    work_experience: str = ""
    projects: str = ""
    skills_raw: str = ""


class ResumeParseResult(StableModel):
    resume_id: str
    target_job: str = ""
    education: str = ""
    experience: str = ""
    work_experience: str = ""
    projects: list[str] = Field(default_factory=list)
    skills: list[SkillEvidence] = Field(default_factory=list)
    need_human_review: bool = False


class ResumeDocumentExtractResult(StableModel):
    file_name: str
    file_type: Literal["pdf", "docx", "txt"]
    raw_text: str
    character_count: int = Field(ge=0)
    education: str = ""
    experience: str = ""
    work_experience: str = ""
    projects: str = ""
    skills_raw: str = ""
    warnings: list[str] = Field(default_factory=list)


class MatchRequest(StableModel):
    resume: ResumeParseRequest
    job_title: str


class MatchResult(StableModel):
    profile_source: Literal["static_baseline", "published_dynamic"] = "static_baseline"
    profile_version: int | None = None
    profile_id: str | None = None
    profile_fingerprint: str | None = None
    resume_id: str
    job_title: str
    match_score: float = Field(ge=0, le=100)
    dimension_scores: dict[str, Annotated[float, Field(ge=0, le=100)] | None]
    dimension_status: dict[str, Literal["met", "not_met", "unknown"]] = Field(default_factory=dict)
    evaluated_dimensions: list[str] = Field(default_factory=list)
    data_completeness: float = Field(default=0, ge=0, le=1)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    advantage_skills: list[str] = Field(default_factory=list)
    priority_skills: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    explanation: list[str] = Field(default_factory=list)
    need_human_review: bool = False


class QualityCheckResult(StableModel):
    passed: bool
    checks: dict[str, Any]

