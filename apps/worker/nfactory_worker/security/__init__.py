"""Security checks of A10 (spec §5, §8.3). Interface: `scan_files`, `Finding`."""

from nfactory_worker.security.secret_scan import Finding, scan_files

__all__ = ["Finding", "scan_files"]
