import hashlib
import re
from dataclasses import dataclass

from app.ingestion.extract import TextUnit

_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class ChunkDraft:
    content: str
    chunk_index: int
    page_start: int
    page_end: int
    section: str


def chunk_units(units: list[TextUnit], size: int, overlap: int) -> list[ChunkDraft]:
    words: list[tuple[str, int, str]] = []
    for unit in units:
        for word in unit.text.split():
            if word:
                words.append((word, unit.page, unit.section))
    if not words or size < 1:
        return []
    step = max(size - overlap, 1)
    drafts: list[ChunkDraft] = []
    start = 0
    while start < len(words):
        window = words[start : start + size]
        drafts.append(
            ChunkDraft(
                content=" ".join(word for word, _, _ in window),
                chunk_index=len(drafts),
                page_start=window[0][1],
                page_end=window[-1][1],
                section=window[0][2],
            )
        )
        if start + size >= len(words):
            break
        start += step
    return drafts


def sparse_term_vector(text: str) -> tuple[list[int], list[float]]:
    counts: dict[int, int] = {}
    for token in _TOKEN.findall(text.lower()):
        index = int(hashlib.sha1(token.encode("utf-8")).hexdigest()[:8], 16)
        counts[index] = counts.get(index, 0) + 1
    if not counts:
        return [0], [0.0]
    indices = sorted(counts)
    return indices, [float(counts[index]) for index in indices]
