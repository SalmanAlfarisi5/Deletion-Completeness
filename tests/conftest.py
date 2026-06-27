"""Make the repository root importable from the tests.

The target modules use top-level imports (e.g. `import config`,
`from certificate.schema import ...`), so the repo root must be on sys.path
regardless of how pytest is invoked. Putting this in tests/conftest.py keeps the
change confined to the tests/ directory.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
