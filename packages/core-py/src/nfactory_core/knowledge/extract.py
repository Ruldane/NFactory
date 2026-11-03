"""Turn an uploaded file into plain text (spec §7.2, ADR-0007).

Uploaded files are untrusted: size, page count and decompressed size are capped
before any parser runs, and every parser failure becomes an `ExtractionError`.
"""

import bisect
import io
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

Kind = Literal["markdown", "text", "code", "pdf", "docx"]

MAX_BYTES = 10 * 1024 * 1024
MAX_UNZIPPED_BYTES = 50 * 1024 * 1024
MAX_PAGES = 500
MAX_CHARS = 2_000_000

CODE_LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".sh": "shell",
    ".sql": "sql",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".css": "css",
    ".html": "html",
}
TEXT_KINDS: dict[str, Kind] = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".rst": "text",
    ".csv": "text",
}
SUPPORTED = sorted({*CODE_LANGUAGES, *TEXT_KINDS, ".pdf", ".docx"})


class ExtractionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Extracted:
    kind: Kind
    text: str
    language: str | None = None
    # 1-based line where each PDF page starts.
    page_starts: tuple[int, ...] = ()

    def page_at(self, line: int) -> int | None:
        if not self.page_starts:
            return None
        return max(1, bisect.bisect_right(self.page_starts, line))


def extract(filename: str, data: bytes) -> Extracted:
    if len(data) > MAX_BYTES:
        raise ExtractionError("file_too_large", "Fichier trop volumineux (10 Mo au maximum).")
    suffix = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    if suffix == ".pdf":
        result = _pdf(data)
    elif suffix == ".docx":
        result = _docx(data)
    elif suffix in TEXT_KINDS:
        result = Extracted(TEXT_KINDS[suffix], _decode(data))
    elif suffix in CODE_LANGUAGES:
        result = Extracted("code", _decode(data), CODE_LANGUAGES[suffix])
    else:
        raise ExtractionError(
            "unsupported_file_type",
            f"Type de fichier non pris en charge. Formats acceptés : {', '.join(SUPPORTED)}.",
        )
    if not result.text.strip():
        raise ExtractionError("empty_document", "Aucun texte à indexer dans ce fichier.")
    if len(result.text) > MAX_CHARS:
        raise ExtractionError("file_too_large", "Texte extrait trop long pour être indexé.")
    return result


def _decode(data: bytes) -> str:
    if b"\x00" in data:
        raise ExtractionError("binary_content", "Ce fichier contient des données binaires.")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return _lines(data.decode(encoding))
        except UnicodeDecodeError:
            continue
    return _lines(data.decode("latin-1"))


def _lines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _pdf(data: bytes) -> Extracted:
    from pypdf import PdfReader  # imported lazily: only PDF uploads pay for it

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ExtractionError("unreadable_document", "PDF protégé par mot de passe.")
        if len(reader.pages) > MAX_PAGES:
            raise ExtractionError(
                "file_too_large", f"PDF trop long ({MAX_PAGES} pages au maximum)."
            )
        pages = [_lines(page.extract_text() or "").strip("\n") for page in reader.pages]
    except ExtractionError:
        raise
    except Exception as exc:  # pypdf raises many types on malformed input
        raise ExtractionError("unreadable_document", "PDF illisible ou endommagé.") from exc
    lines: list[str] = []
    starts: list[int] = []
    for page in pages:
        starts.append(len(lines) + 1)
        lines.extend(page.split("\n") if page else [""])
    return Extracted("pdf", "\n".join(lines) + "\n", page_starts=tuple(starts))


def _docx(data: bytes) -> Extracted:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            unzipped = sum(info.file_size for info in archive.infolist())
    except zipfile.BadZipFile as exc:
        raise ExtractionError("unreadable_document", "Document Word illisible.") from exc
    if unzipped > MAX_UNZIPPED_BYTES:
        raise ExtractionError("file_too_large", "Document Word trop volumineux une fois ouvert.")
    import docx  # imported lazily: only Word uploads pay for it
    from docx.table import Table

    try:
        document = docx.Document(io.BytesIO(data))
        blocks: list[str] = []
        for item in document.iter_inner_content():
            if isinstance(item, Table):
                rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in item.rows]
                blocks.append("\n".join(rows))
                continue
            text = item.text.strip()
            if text:
                blocks.append(_heading_prefix(item.style.name if item.style else "") + text)
    except Exception as exc:  # python-docx raises many types on malformed input
        raise ExtractionError("unreadable_document", "Document Word illisible.") from exc
    return Extracted("docx", "\n\n".join(blocks) + "\n")


def _heading_prefix(style: str) -> str:
    """'Heading 2' / 'Titre 2' become '## '; 'Title' becomes '# '."""
    name = style.strip().lower()
    if name in ("title", "titre"):
        return "# "
    for word in ("heading ", "titre "):
        if name.startswith(word) and name[len(word) :].isdigit():
            return "#" * min(6, int(name[len(word) :])) + " "
    return ""
