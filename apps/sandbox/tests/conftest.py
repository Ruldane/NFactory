"""Make the sandbox package importable: it is copied into its image, not installed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
