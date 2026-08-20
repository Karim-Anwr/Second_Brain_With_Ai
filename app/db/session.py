"""SQLAlchemy 2.x engine and request-session lifecycle helpers.

The engine is lazy: importing the application, running Phase 1 routes, and
starting FastAPI do not establish a database connection. Schema creation is
intentionally delegated to Alembic migrations, never ``metadata.create_all``.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


class DatabaseConfigurationError(RuntimeError):
    """Raised when a database-backed operation is requested without DATABASE_URL."""


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def build_engine(database_url: str) -> Engine:
    """Build a synchronous PostgreSQL engine without opening a connection."""
    if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise DatabaseConfigurationError("DATABASE_URL must use a PostgreSQL URL.")
    return create_engine(database_url, pool_pre_ping=True, future=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build non-autocommit request sessions for the supplied engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_engine() -> Engine:
    """Return the configured lazy singleton engine, without connecting to PostgreSQL."""
    global _engine
    if _engine is None:
        if not settings.database_url:
            raise DatabaseConfigurationError("DATABASE_URL must be configured for database-backed operations.")
        _engine = build_engine(settings.database_url)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the configured lazy singleton session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = build_session_factory(get_engine())
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """Yield and always close a request-scoped database session."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def close_database() -> None:
    """Dispose an existing engine pool during shutdown; never creates one."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
