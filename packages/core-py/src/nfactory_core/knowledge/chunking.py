"""Cut extracted text into searchable chunks that remember where they came from.

Documents are cut by section, Python by function and class, other code by block.
Each chunk keeps its 1-based line range in the extracted text so a citation can point
at the exact lines; long pieces are windowed with a small overlap.
"""

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass

from nfactory_core.knowledge.extract import Extracted

MAX_CHARS = 1500
OVERLAP_LINES = 2

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_SYMBOLS = [
    re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([\w$-]+)"),
    re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+([\w$]+)"),
    re.compile(r"^\s*(?:async\s+)?def\s+(\w+)"),
    re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?(\w+)"),
    re.compile(r"^\s*(?:pub\s+)?fn\s+(\w+)"),
]


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    content: str
    start_line: int
    end_line: int
    section: str | None = None
    symbol: str | None = None
    page: int | None = None


@dataclass(frozen=True)
class _Segment:
    start: int  # 1-based, inclusive
    end: int
    section: str | None = None
    symbol: str | None = None


def chunk(source: Extracted, max_chars: int = MAX_CHARS) -> list[Chunk]:
    lines = source.text.split("\n")
    if source.kind in ("markdown", "docx"):
        segments = _sections(lines)
    elif source.kind == "code" and source.language == "python":
        segments = _python(source.text, lines)
    elif source.kind == "code":
        segments = _blocks(lines, max_chars, code=True)
    else:
        segments = _blocks(lines, max_chars, code=False, pages=source.page_starts)
    chunks: list[Chunk] = []
    for segment in segments:
        for start, end, content in _windows(lines, segment, max_chars):
            chunks.append(
                Chunk(
                    ordinal=len(chunks),
                    content=content,
                    start_line=start,
                    end_line=end,
                    section=segment.section,
                    symbol=segment.symbol,
                    page=source.page_at(start),
                )
            )
    return chunks


def _sections(lines: list[str]) -> list[_Segment]:
    """One segment per Markdown heading; the section is the heading path."""
    stack: list[tuple[int, str]] = []
    segments: list[_Segment] = []
    start, section, fenced = 1, None, False
    for number, line in enumerate(lines, start=1):
        if _FENCE.match(line):
            fenced = not fenced
        heading = None if fenced else _HEADING.match(line)
        if not heading:
            continue
        segments.append(_Segment(start, number - 1, section))
        level = len(heading.group(1))
        stack = [(lv, title) for lv, title in stack if lv < level] + [(level, heading.group(2))]
        start, section = number, " > ".join(title for _, title in stack)
    segments.append(_Segment(start, len(lines), section))
    return segments


def _python(text: str, lines: list[str]) -> list[_Segment]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _blocks(lines, MAX_CHARS, code=True)
    segments: list[_Segment] = []
    module: list[int] = []  # [start, end] of the current run of module-level code

    def flush() -> None:
        if module:
            segments.append(_Segment(module[0], module[1]))
            module.clear()

    for node in tree.body:
        end = node.end_lineno or node.lineno
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            flush()
            start = min([d.lineno for d in node.decorator_list] + [node.lineno])
            segments.append(_Segment(start, end, symbol=node.name))
        elif module:
            module[1] = end
        else:
            module.extend([node.lineno, end])
    flush()
    return segments


def _blocks(
    lines: list[str], max_chars: int, *, code: bool, pages: tuple[int, ...] = ()
) -> list[_Segment]:
    """Blank-line blocks packed up to `max_chars`; a symbol or a page starts a new one."""
    blocks: list[_Segment] = []
    start = None
    for number, line in enumerate([*lines, ""], start=1):
        if line.strip() and start is None:
            start = number
        new_page = number in pages and start is not None and start < number
        if start is not None and (not line.strip() or new_page):
            end = number - 1
            blocks.append(
                _Segment(start, end, symbol=_symbol(lines[start - 1 : end]) if code else None)
            )
            start = number if new_page and line.strip() else None
    packed: list[_Segment] = []
    for block in blocks:
        last = packed[-1] if packed else None
        same_page = not pages or not any(last and last.start < p <= block.start for p in pages)
        size = sum(len(x) + 1 for x in lines[(last.start if last else 1) - 1 : block.end])
        if last and block.symbol is None and same_page and size <= max_chars:
            packed[-1] = _Segment(last.start, block.end, symbol=last.symbol)
        else:
            packed.append(block)
    return packed


def _symbol(block: list[str]) -> str | None:
    for line in block:
        for pattern in _SYMBOLS:
            match = pattern.match(line)
            if match:
                return match.group(1)
    return None


def _windows(lines: list[str], segment: _Segment, max_chars: int) -> Iterator[tuple[int, int, str]]:
    """Split a segment into pieces of at most `max_chars`, sharing OVERLAP_LINES lines."""
    start, end = segment.start, segment.end
    while start <= end and not lines[start - 1].strip():
        start += 1
    while end >= start and not lines[end - 1].strip():
        end -= 1
    while start <= end:
        stop, size = start, len(lines[start - 1])
        while stop < end and size + 1 + len(lines[stop]) <= max_chars:
            size += 1 + len(lines[stop])
            stop += 1
        if size > max_chars:  # one line longer than a chunk: cut the line itself
            line = lines[start - 1]
            for offset in range(0, len(line), max_chars):
                yield start, start, line[offset : offset + max_chars]
        else:
            yield start, stop, "\n".join(lines[start - 1 : stop]).strip()
        if stop >= end:
            return
        start = max(start + 1, stop - OVERLAP_LINES + 1)
