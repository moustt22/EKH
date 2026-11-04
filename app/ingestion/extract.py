import io
from dataclasses import dataclass

import pymupdf
from docx import Document


@dataclass(frozen=True)
class TextUnit:
    text: str
    page: int
    section: str


def extract_text(file_type: str, data: bytes) -> list[TextUnit]:
    if file_type == "pdf":
        return _extract_pdf(data)
    if file_type == "docx":
        return _extract_docx(data)
    raise ValueError("Unsupported file type")


def _extract_pdf(data: bytes) -> list[TextUnit]:
    units: list[TextUnit] = []
    with pymupdf.open(stream=data, filetype="pdf") as document:
        for page in document:
            lines = _pdf_lines(page)
            if not lines:
                continue
            median = sorted(size for _, size in lines)[len(lines) // 2]
            section = ""
            for text, size in lines:
                if _is_heading(text, size, median):
                    section = text[:300]
                units.append(TextUnit(text=text, page=page.number + 1, section=section))
    return units


def _pdf_lines(page) -> list[tuple[str, float]]:
    lines: list[tuple[str, float]] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(span.get("text", "") for span in spans).strip()
            if not text:
                continue
            size = max((float(span.get("size", 0)) for span in spans), default=0)
            lines.append((text, size))
    return lines


def _is_heading(text: str, size: float, median: float) -> bool:
    return size >= median + 1.5 and len(text) <= 80 and not text.endswith(".")


def _extract_docx(data: bytes) -> list[TextUnit]:
    document = Document(io.BytesIO(data))
    units: list[TextUnit] = []
    section = ""
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style_name = paragraph.style.name if paragraph.style is not None else ""
        if style_name.startswith("Heading"):
            section = text[:300]
        units.append(TextUnit(text=text, page=1, section=section))
    return units
