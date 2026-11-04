import hashlib
from pathlib import Path

from app.core.documents import MAX_UPLOAD_BYTES

PDF_TYPE = "application/pdf"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
CONTENT_TYPES = {"pdf": PDF_TYPE, "docx": DOCX_TYPE}


class FileValidationError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def validate_upload(filename: str | None, data: bytes) -> tuple[str, str, str]:
    if not filename or not filename.strip():
        raise FileValidationError(400, "A file name is required")
    safe_name = _safe_filename(filename)
    extension = Path(safe_name).suffix.lower()
    file_type = extension.lstrip(".")
    if file_type not in CONTENT_TYPES:
        raise FileValidationError(400, "Only PDF and DOCX files are accepted")
    if not data:
        raise FileValidationError(400, "The file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise FileValidationError(413, "File exceeds the 25 MB limit")
    if file_type == "pdf" and not data.startswith(b"%PDF"):
        raise FileValidationError(400, "The file is not a valid PDF")
    if file_type == "docx" and not data.startswith(b"PK"):
        raise FileValidationError(400, "The file is not a valid DOCX")
    return file_type, CONTENT_TYPES[file_type], safe_name


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def read_limited(upload, limit: int = MAX_UPLOAD_BYTES) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise FileValidationError(413, "File exceeds the 25 MB limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _safe_filename(filename: str) -> str:
    base = Path(filename.replace("\\", "/")).name.strip()
    cleaned = "".join(char if char.isalnum() or char in ".-_" else "_" for char in base)
    cleaned = cleaned.strip("._") or "document"
    return cleaned[:200]
