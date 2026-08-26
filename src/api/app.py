from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ..schemas import JDParseRequest, JDParseResult, MatchRequest, MatchResult, ResumeParseRequest, ResumeParseResult
from .service import get_services
from .integration_service import get_system_data


app = FastAPI(
    title="挑战杯岗位技能核心算法API",
    version="1.0.0",
    description="稳定Schema：JD解析、简历解析、人岗匹配、岗位与技能数据接口。",
)

cors_origins = ["http://127.0.0.1:5173", "http://localhost:5173"]
cors_origins.extend(
    origin.strip().rstrip("/")
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(cors_origins)),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.post("/api/jd/parse", response_model=JDParseResult)
def parse_jd(request: JDParseRequest) -> JDParseResult:
    return get_services().jd_parser.parse(request)


@app.post("/api/resume/parse", response_model=ResumeParseResult)
def parse_resume(request: ResumeParseRequest) -> ResumeParseResult:
    return get_services().resume_parser.parse(request)


@app.post("/api/match", response_model=MatchResult)
def match_resume(request: MatchRequest) -> MatchResult:
    services = get_services()
    parsed = services.resume_parser.parse(request.resume)
    return services.matching_engine.match(parsed, request.job_title)


@app.get("/api/jobs")
def list_jobs() -> dict:
    services = get_services()
    rows = services.loader.load_jds()
    counts = {}
    for row in rows:
        title = str(row.get("standard_job_title", "")).strip()
        if title:
            counts[title] = counts.get(title, 0) + 1
    return {
        "data_version": services.loader.version.get("data_version"),
        "jobs": [{"standard_job_title": title, "jd_count": counts[title]} for title in sorted(counts)],
    }


@app.get("/api/skills")
def list_skills() -> dict:
    services = get_services()
    return {
        "data_version": services.loader.version.get("data_version"),
        "skills": [
            {"skill_id": item.skill_id, "standard_skill_name": item.name, "skill_type": item.category}
            for item in sorted(services.skill_index.skills.values(), key=lambda value: value.skill_id)
        ],
    }


@app.get("/api/system/overview")
def system_overview() -> dict:
    return get_system_data().overview()


@app.get("/api/job-analysis/{job_title}")
def job_analysis(job_title: str) -> dict:
    return get_system_data().job_analysis(job_title)


@app.get("/api/graph/job/{job_title}")
def graph_for_job(job_title: str) -> dict:
    return get_system_data().graph.for_job(job_title)


@app.get("/api/graph/skill/{skill_id}")
def graph_for_skill(skill_id: str) -> dict:
    return get_system_data().graph.for_skill(skill_id)


@app.get("/api/evolution/job/{job_title}")
def evolution_for_job(job_title: str) -> dict:
    return get_system_data().evolution.for_job(job_title)


@app.get("/api/emerging-jobs")
def emerging_jobs() -> dict:
    return get_system_data().emerging_list()


@app.get("/api/emerging-jobs/{candidate_id}")
def emerging_job_detail(candidate_id: str) -> dict:
    value = get_system_data().emerging_detail(candidate_id)
    if value is None:
        raise HTTPException(status_code=404, detail="未找到该新岗位候选")
    return value
