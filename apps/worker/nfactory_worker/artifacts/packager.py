"""Reproducible ZIP of a workspace: same files in, same bytes out."""

import io
import zipfile

from nfactory_core.workspace import Workspace

# Internal run data (JUnit reports...) is not part of the delivery.
EXCLUDED_PREFIXES = (".nfactory/",)
_FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def zip_workspace(workspace: Workspace) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in workspace.files():
            if relative.startswith(EXCLUDED_PREFIXES):
                continue
            info = zipfile.ZipInfo(relative, date_time=_FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, workspace.read_bytes(relative))
    return buffer.getvalue()
