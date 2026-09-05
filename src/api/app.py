from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from ..schemas import JDParseRequest, JDParseResult, MatchRequest, MatchResult, ResumeDocumentExtractResult, ResumeParseRequest, ResumeParseResult
from ..core.resume_document import MAX_FILE_BYTES, ResumeDocumentError, extract_resume_document
from .service import get_services
from .integration_service import get_system_data
from .closure import router as closure_router, get_closure
from ..closure.settings import production, allowed_origins, validate_auth
from ..closure.repository import PublishedProfileRepository, ProfileReadError
from ..closure.service import ClosureError


@asynccontextmanager
async def lifespan(_app):
    validate_auth()
    if production():
        service = get_closure()
        service.check_storage()
        PublishedProfileRepository(service.db_path).latest_by_job()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="挑战杯岗位技能核心算法API",
    version="1.0.0",
    description="稳定Schema：JD解析、简历解析、人岗匹配、岗位与技能数据接口。",
)

cors_origins = allowed_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(cors_origins)),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(closure_router)


@app.middleware("http")
async def prevent_stale_api_cache(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(sqlite3.Error)
async def storage_error_handler(_request, _exc):
    return JSONResponse(status_code=503, content={"detail": "Closure storage unavailable; no successful write acknowledged"})


@app.get("/api/health/ready")
def readiness():
    validate_auth()
    service = get_closure()
    service.check_storage()
    PublishedProfileRepository(service.db_path).latest_by_job()
    return {"status": "ready", "storage": "ok"}


@app.exception_handler(ClosureError)
async def closure_error_handler(_request, exc: ClosureError):
    return JSONResponse(status_code=exc.status, content={"detail": str(exc)})


@app.exception_handler(ProfileReadError)
async def profile_read_error_handler(_request, exc: ProfileReadError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.post("/api/jd/parse", response_model=JDParseResult)
def parse_jd(request: JDParseRequest) -> JDParseResult:
    return get_services().jd_parser.parse(request)


@app.post("/api/resume/parse", response_model=ResumeParseResult)
def parse_resume(request: ResumeParseRequest) -> ResumeParseResult:
    services = get_services()
    effective = services.matching_engine.effective_profiles.get_effective_job_profile(request.target_job)
    requirements = effective.get("matching_profile") or {}
    return services.resume_parser.parse(request, job_requirements=requirements)


@app.post("/api/resume/extract", response_model=ResumeDocumentExtractResult)
async def extract_resume(file: UploadFile = File(...)) -> ResumeDocumentExtractResult:
    try:
        data = await file.read(MAX_FILE_BYTES + 1)
        return extract_resume_document(file.filename or "resume", data)
    except ResumeDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()


@app.post("/api/match", response_model=MatchResult)
def match_resume(request: MatchRequest) -> MatchResult:
    services = get_services()
    parsed = services.resume_parser.parse(request.resume)
    return services.matching_engine.match(parsed, request.job_title)


@app.get("/api/jobs")
def list_jobs() -> dict:
    services = get_services()
    counts = services.loader.job_analysis_counts()
    effective = services.matching_engine.effective_profiles
    publications = effective.published_profiles()
    for title, published in publications.items():
        counts[title] = published["source_job_count"]
    return {
        "data_version": services.loader.job_analysis_data_version(),
        "jobs": [{"standard_job_title": title, "jd_count": counts[title],
                  **effective.metadata(effective.get_effective_job_profile(title, publications))} for title in sorted(counts)],
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


@app.get("/api/multi-source")
def multi_source() -> dict:
    return get_system_data().multi_source()


@app.get("/api/job-changes")
def job_changes() -> dict:
    return get_system_data().job_changes()


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


# The free Render deployment uses one service and one public URL.  The Vite
# bundle is committed deliberately so the Python runtime does not need Node.js.
_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@app.get("/{frontend_path:path}", include_in_schema=False)
def serve_frontend(frontend_path: str):
    if frontend_path == "api" or frontend_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    candidate = (_frontend_dist / frontend_path).resolve()
    if frontend_path and _frontend_dist.resolve() in candidate.parents and candidate.is_file():
        headers = {"Cache-Control": "no-cache"} if frontend_path.startswith("data/") else None
        return FileResponse(candidate, headers=headers)
    index = _frontend_dist / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="Frontend build is unavailable")
    return FileResponse(index)
