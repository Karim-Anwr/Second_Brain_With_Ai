"""Minimal authenticated identity derived from a verified token and User record."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CurrentUser:
    """Authentication identity only; it conveys no ownership or authorization grants."""

    id: UUID
