"""Additive local P1 endpoints. Writes are opt-in and loopback-only, not public review auth."""
import os
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ..closure.service import ClosureService
from ..closure.repository import closure_database_path
from .service import get_services


@lru_cache(maxsize=1)
def get_closure():
    core = get_services()
    return ClosureService(core, closure_database_path(core.loader.project_root))


def local_write(request: Request):
    if os.getenv("P1_CLOSURE_WRITES") != "1" or not request.client or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(403, "P1 writes require an explicitly enabled local loopback test environment")
    origin = request.headers.get("origin")
    if origin and origin not in {"http://127.0.0.1:5173", "http://localhost:5173"}:
        raise HTTPException(403, "untrusted origin")


router = APIRouter(prefix="/api/closure", tags=["P1 local closure"])
write_guard = [Depends(local_write)]


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str = Field(min_length=1, max_length=200)
    original_title: str = Field(min_length=1, max_length=500)
    standard_job_title: str = ""
    standardization_status: str = ""
    responsibilities: str = ""
    required_skills_raw: str = ""
    bonus_skills_raw: str = ""
    industry: str = ""
    scenario: str = ""
    business_context: str = ""
    technical_domain: str = ""
    company: str = ""
    source: str = ""
    url: str = ""
    published_at: str | None = None
    collected_at: str | None = None
    first_seen_at: str | None = None


class VersionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    expected_revision: int = Field(ge=0)


class ManualInput(VersionInput):
    definition: dict[str, Any]


class ActionInput(VersionInput):
    action: str
    reviewer: str | None = None
    note: str = ""
    acknowledge_gaps: bool = False


class UpdateInput(BaseModel):
    job_title: str = Field(min_length=1)


@router.post("/evidence", dependencies=write_guard)
def add_evidence(body: EvidenceInput, service=Depends(get_closure)):
    return service.add_evidence(body.model_dump())


@router.get("/evidence/{job_id}")
def evidence(job_id: str, service=Depends(get_closure)):
    return service.evidence(job_id)


@router.post("/discovery/run", dependencies=write_guard)
def discover(service=Depends(get_closure)):
    return service.discover()


@router.get("/candidates")
def candidates(service=Depends(get_closure)):
    return service.list_entities("candidate")


@router.post("/profiles/run", dependencies=write_guard)
def update(body: UpdateInput, service=Depends(get_closure)):
    return service.run_update(body.job_title)


@router.get("/{kind}/{identifier}")
def detail(kind: str, identifier: str, service=Depends(get_closure)):
    return service.get(kind, identifier)


@router.get("/{kind}/{identifier}/versions")
def versions(kind: str, identifier: str, service=Depends(get_closure)):
    return service.history(kind, identifier)


@router.get("/{kind}/{identifier}/published")
def published(kind: str, identifier: str, service=Depends(get_closure)):
    return service.published(kind, identifier)


@router.get("/{kind}/{identifier}/diff")
def diff(kind: str, identifier: str, before: int, after: int, service=Depends(get_closure)):
    return service.diff(kind, identifier, before, after)


@router.post("/{kind}/{identifier}/manual", dependencies=write_guard)
def manual(kind: str, identifier: str, body: ManualInput, service=Depends(get_closure)):
    return service.edit(kind, identifier, body.definition, body.expected_version, body.expected_revision)


@router.post("/{kind}/{identifier}/actions", dependencies=write_guard)
def action(kind: str, identifier: str, body: ActionInput, service=Depends(get_closure)):
    values = body.model_dump()
    action_name = values.pop("action")
    return service.action(kind, identifier, action_name, **values)
