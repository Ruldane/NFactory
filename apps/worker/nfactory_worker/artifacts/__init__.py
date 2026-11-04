"""Delivery files. Interface: zip_workspace, provenance_manifest (AI-generated marking),
ArtifactStore, LocalArtifactStore."""

from nfactory_worker.artifacts.packager import zip_workspace
from nfactory_worker.artifacts.provenance import (
    AI_NOTICE,
    DIGITAL_SOURCE_TYPE,
    PROVENANCE_FILE,
    provenance_manifest,
)
from nfactory_worker.artifacts.store import (
    ArtifactStore,
    LocalArtifactStore,
    StoredArtifact,
    mime_for,
)

__all__ = [
    "AI_NOTICE",
    "DIGITAL_SOURCE_TYPE",
    "PROVENANCE_FILE",
    "ArtifactStore",
    "LocalArtifactStore",
    "StoredArtifact",
    "mime_for",
    "provenance_manifest",
    "zip_workspace",
]
