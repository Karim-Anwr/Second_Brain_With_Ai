"""Shared SQLAlchemy declarative base for migration-driven persistence models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class only; Phase 2.1 deliberately defines no application tables."""
