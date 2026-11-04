"""Reproducible ZIP of a workspace: same files in, same bytes out."""

import io
import zipfile

from nfactory_core.workspace import Workspace
from nfactory_worker.artifacts.provenance import PROVENANCE_FILE, delivered_files

_FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def zip_workspace(workspace: Workspace) -> bytes:
    """The delivered files, plus the AI-generated manifest when the run wrote one."""
    paths = delivered_files(workspace)
    if PROVENANCE_FILE in workspace.files():
        paths.append(PROVENANCE_FILE)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in paths:
            info = zipfile.ZipInfo(relative, date_time=_FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, workspace.read_bytes(relative))
    return buffer.getvalue()
