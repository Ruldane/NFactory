"""Artifact storage. Local disk now; an S3-compatible adapter can follow (spec §4)."""

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_RUN = re.compile(r"^[A-Za-z0-9_-]+$")

MIME_TYPES = {
    ".zip": "application/zip",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown",
    ".diff": "text/x-diff",
}


@dataclass(frozen=True)
class StoredArtifact:
    filename: str
    mime: str
    storage_key: str  # "<run_id>/<filename>", relative to the store root
    path: str
    checksum: str  # "sha256:<hex>"
    size: int


class ArtifactStore(Protocol):
    def save(self, run_id: str, filename: str, data: bytes) -> StoredArtifact: ...


def mime_for(filename: str) -> str:
    return MIME_TYPES.get(Path(filename).suffix.lower(), "application/octet-stream")


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, run_id: str, filename: str, data: bytes) -> StoredArtifact:
        if not _RUN.fullmatch(run_id) or not _FILENAME.fullmatch(filename):
            raise ValueError(f"Invalid artifact name: {run_id}/{filename}")
        target = self.root / run_id / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        # Write then rename, so a crash never leaves a half-written artifact behind.
        partial = target.with_name(target.name + ".part")
        partial.write_bytes(data)
        os.replace(partial, target)
        return StoredArtifact(
            filename=filename,
            mime=mime_for(filename),
            storage_key=f"{run_id}/{filename}",
            path=str(target),
            checksum="sha256:" + hashlib.sha256(data).hexdigest(),
            size=len(data),
        )
