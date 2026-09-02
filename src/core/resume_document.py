"""Safe, in-memory text extraction for user-supplied resumes."""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from ..schemas import ResumeDocumentExtractResult

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TEXT_CHARS = 200_000
MAX_PDF_PAGES = 100
MAX_DOCX_UNCOMPRESSED = 32 * 1024 * 1024
MAX_DOCX_ENTRIES = 1000
SUPPORTED = {".pdf": "pdf", ".docx": "docx", ".txt": "txt"}


class ResumeDocumentError(ValueError):
    pass


def _clean_text(value: str) -> str:
    value = value.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    value = "".join(char for char in value if char in "\n\t" or ord(char) >= 32)
    value = re.sub(r"[ \t]+", " ", value)
    return re.sub(r"\n{3,}", "\n\n", value).strip()[:MAX_TEXT_CHARS]


def _extract_pdf(data: bytes) -> tuple[str, list[str]]:
    if not data.startswith(b"%PDF-"):
        raise ResumeDocumentError("文件扩展名是 PDF，但内容不是有效 PDF。")
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ResumeDocumentError(f"PDF 页数不能超过 {MAX_PDF_PAGES} 页。")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except ResumeDocumentError:
        raise
    except Exception as exc:
        raise ResumeDocumentError("PDF 无法解析，可能已损坏或加密。") from exc
    warnings = [] if text.strip() else ["该 PDF 没有可提取的文本层，可能是扫描件；请使用 OCR 后重试或手工粘贴文本。"]
    return text, warnings


def _extract_docx(data: bytes) -> tuple[str, list[str]]:
    if not data.startswith(b"PK"):
        raise ResumeDocumentError("文件扩展名是 DOCX，但内容不是有效 Word 文档。")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_DOCX_ENTRIES or sum(item.file_size for item in infos) > MAX_DOCX_UNCOMPRESSED:
                raise ResumeDocumentError("DOCX 解压后体积异常，已拒绝解析。")
            if "word/document.xml" not in archive.namelist():
                raise ResumeDocumentError("DOCX 缺少正文结构。")
        document = Document(io.BytesIO(data))
        parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        for table in document.tables:
            for row in table.rows:
                line = "\t".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if line:
                    parts.append(line)
        return "\n".join(parts), []
    except ResumeDocumentError:
        raise
    except Exception as exc:
        raise ResumeDocumentError("DOCX 无法解析，可能已损坏或包含不支持的结构。") from exc


def _extract_txt(data: bytes) -> tuple[str, list[str]]:
    if b"\x00" in data:
        raise ResumeDocumentError("TXT 中包含二进制内容，已拒绝解析。")
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding), []
        except UnicodeDecodeError:
            continue
    raise ResumeDocumentError("TXT 编码无法识别，请保存为 UTF-8 后重试。")


HEADINGS = {
    "education": ("教育经历", "教育背景", "学历信息"),
    "work_experience": ("工作经历", "工作经验", "职业经历", "实习经历"),
    "projects": ("项目经历", "项目经验", "代表项目"),
    "skills_raw": ("专业技能", "技能清单", "技能特长", "核心技能", "个人技能"),
}


def _draft_fields(text: str) -> dict[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    heading_lookup = {heading.lower(): field for field, names in HEADINGS.items() for heading in names}
    sections = {field: [] for field in HEADINGS}
    active = None
    for line in lines:
        key = re.sub(r"[：:丨|\s]", "", line).lower()
        matched = next((field for heading, field in heading_lookup.items() if key == heading), None)
        if matched:
            active = matched
        elif active:
            sections[active].append(line)
    education = "\n".join(sections["education"])
    if not education:
        education = next((line for line in lines if re.search(r"博士|硕士|本科|大专|专科", line)), "")
    experience = next((match.group(0) for line in lines
                       if (match := re.search(r"(?:\d+(?:\.\d+)?\s*年(?:以上)?(?:工作|开发|项目)?经验|应届(?:毕业生)?)", line))), "")
    work = "\n".join(sections["work_experience"])
    projects = "\n".join(sections["projects"])
    skills = "\n".join(sections["skills_raw"])
    if not any((work, projects, skills)):
        work = text
    return dict(education=education, experience=experience, work_experience=work,
                projects=projects, skills_raw=skills)


def extract_resume_document(filename: str, data: bytes) -> ResumeDocumentExtractResult:
    safe_name = Path(filename or "resume").name
    suffix = Path(safe_name).suffix.lower()
    if suffix == ".doc":
        raise ResumeDocumentError("暂不支持旧版 .doc，请在 Word 中另存为 .docx 后上传。")
    if suffix not in SUPPORTED:
        raise ResumeDocumentError("仅支持 PDF、DOCX 和 TXT 格式。")
    if not data:
        raise ResumeDocumentError("上传文件为空。")
    if len(data) > MAX_FILE_BYTES:
        raise ResumeDocumentError("文件不能超过 8MB。")
    raw, warnings = {".pdf": _extract_pdf, ".docx": _extract_docx, ".txt": _extract_txt}[suffix](data)
    text = _clean_text(raw)
    if not text:
        if warnings:
            return ResumeDocumentExtractResult(file_name=safe_name, file_type=SUPPORTED[suffix],
                                               raw_text="", character_count=0, warnings=warnings)
        raise ResumeDocumentError("没有从文件中提取到可用文本。")
    return ResumeDocumentExtractResult(file_name=safe_name, file_type=SUPPORTED[suffix], raw_text=text,
                                       character_count=len(text), warnings=warnings, **_draft_fields(text))
