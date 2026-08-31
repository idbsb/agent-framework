"""Read-only quality preview and file capability boundary. No database writes."""
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from .closure import EvidenceInput
from .integration_service import get_system_data
from ..quality.science import quality_report
from ..core.resume_files import capabilities, parse_file, FileInputError, MAX_FILE_BYTES

router = APIRouter(tags=['P2 read-only quality'])


class QualityRow(EvidenceInput):
    dataset_notice: str = ''


class QualityPreview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    rows: list[QualityRow] = Field(max_length=500)


@router.get('/api/quality/report')
def report():
    return get_system_data().data_quality()


@router.post('/api/quality/preview')
def preview(body: QualityPreview):
    try:
        return quality_report([r.model_dump() for r in body.rows])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get('/api/resume/file/capabilities')
def file_capabilities():
    return capabilities()


@router.post('/api/resume/file/preview')
async def file_preview(request: Request, filename: str = Query(min_length=1, max_length=255)):
    # Raw binary request avoids requiring uninstalled multipart. No disk writes.
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_FILE_BYTES:
            raise HTTPException(413, dict(code='FILE_TOO_LARGE', message='文件超过 5 MiB 限制。'))
        chunks.append(chunk)
    try:
        return parse_file(filename, request.headers.get('content-type', ''), b''.join(chunks))
    except FileInputError as exc:
        raise HTTPException(exc.status, dict(code=exc.code, message=str(exc))) from exc
