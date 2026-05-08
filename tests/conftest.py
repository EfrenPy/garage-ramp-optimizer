"""Shared pytest configuration.

Adds the project root to sys.path so the tests can `import ramp_optimizer`
without an editable install.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# Force matplotlib to a non-interactive backend before the test suite
# imports anything that might pull in pyplot.  Mirrors what
# ramp_optimizer.py does at import time, but defensive in case a test
# ends up importing matplotlib first.
os.environ.setdefault("MPLBACKEND", "Agg")
