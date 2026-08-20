"""Shared database configuration helpers for application and Alembic tooling."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_database_url_from_environment(project_root: Path = PROJECT_ROOT) -> str | None:
    """Return DATABASE_URL with process environment taking precedence over `.env`."""
    if "DATABASE_URL" in os.environ:
        return os.environ["DATABASE_URL"]
    return dotenv_values(project_root / ".env").get("DATABASE_URL")
