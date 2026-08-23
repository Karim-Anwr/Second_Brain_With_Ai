"""Explicit classification markers for quarantined root/global resource APIs.

Phase 4 does not alter legacy behavior or migrate legacy data.  The marker is
intentionally a no-op: it makes the remaining unscoped APIs auditable while
static tests prevent new production entry points from using them silently.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar


F = TypeVar("F", bound=Callable)


def legacy_global_resource_path(category: str) -> Callable[[F], F]:
    """Mark an unscoped resource API as legacy/test-only compatibility code.

    The decorator does not wrap or otherwise alter the callable.  New
    production multi-user behavior must use the corresponding owner-aware API.
    """

    def mark(function: F) -> F:
        setattr(function, "__legacy_global_resource_path__", category)
        return function

    return mark
