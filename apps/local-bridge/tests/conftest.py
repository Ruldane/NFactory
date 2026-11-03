"""Make the bridge package importable: it runs on the user's machine, it is not installed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
