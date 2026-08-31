"""File parser boundary only. No optional parser is installed or silently substituted."""
from pathlib import PurePosixPath

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 100_000
MIME_TYPES = {'.pdf': 'application/pdf', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}


class FileInputError(ValueError):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code = status, code


def capabilities():
    return dict(pdf=dict(supported=False, status='dependency_required', proposal='pypdf'),
                docx=dict(supported=False, status='dependency_required', proposal='python-docx'),
                text=dict(supported=True, endpoint='/api/resume/parse'), ocr_supported=False,
                max_file_bytes=MAX_FILE_BYTES, max_text_chars=MAX_TEXT_CHARS, requires_user_confirmation=True,
                message='PDF/DOCX 解析依赖待批准，暂不接受文件解析。请使用现有文本输入；不会自动上传或保存文件。')


def parse_file(filename, mime, content):
    """Future adapter returns extracted text and editable fields, never matches/persists.

    A parser integration must bound decompression/pages/text, reject corrupt/encrypted
    input, return OCR_REQUIRED for textless PDFs, and preserve explicit user confirmation.
    Until approved, this boundary returns an honest unsupported result (not empty success).
    """
    suffix = PurePosixPath(filename).suffix.lower()
    if '/' in filename or '\\' in filename or suffix not in MIME_TYPES or mime.split(';')[0].strip().lower() != MIME_TYPES.get(suffix):
        raise FileInputError(415, 'UNSUPPORTED_FILE_TYPE', '只接受声明类型一致的 PDF/DOCX 文件，不支持宏文档。')
    if len(content) > MAX_FILE_BYTES:
        raise FileInputError(413, 'FILE_TOO_LARGE', '文件超过 5 MiB 限制。')
    if not content:
        raise FileInputError(422, 'EMPTY_FILE', '文件为空。')
    raise FileInputError(501, 'DEPENDENCY_REQUIRED', capabilities()['message'])
