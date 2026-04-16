"""
NutriTrack — Environment Loader
================================
Loads key/value pairs from project-level .env into process environment.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_project_env() -> None:
    """Load .env from project root without overriding existing variables."""
    # .../NutriTrack_Source_Code/nutritrack/utils/env_loader.py -> project root
    root = Path(__file__).resolve().parents[2]
    env_file = root / ".env"

    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue

        # Keep explicit shell values if already provided.
        os.environ.setdefault(key, value)
