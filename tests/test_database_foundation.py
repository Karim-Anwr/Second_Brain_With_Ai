"""Focused Phase 2.1 tests that do not require a live PostgreSQL instance."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings, settings
from app.db.configuration import get_database_url_from_environment
from app.db import session as database_session


TEST_DATABASE_URL = "postgresql+psycopg://second_brain:testing@localhost:5432/second_brain_test"


def test_settings_loads_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)

    loaded = Settings()

    assert loaded.database_url == TEST_DATABASE_URL


def test_sqlalchemy_engine_and_session_factory_construct_without_connecting():
    engine = database_session.build_engine(TEST_DATABASE_URL)
    factory = database_session.build_session_factory(engine)
    session = factory()

    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert session.bind.url.username == "second_brain"
        assert session.bind.url.password == "testing"
        assert session.bind.url.database == "second_brain_test"
    finally:
        session.close()
        engine.dispose()


def test_sqlalchemy_engine_rejects_postgresql_url_without_psycopg_driver():
    with pytest.raises(database_session.DatabaseConfigurationError, match="postgresql\\+psycopg"):
        database_session.build_engine("postgresql://second_brain:testing@localhost:5432/second_brain_test")


def test_fastapi_database_dependency_yields_request_scoped_session(monkeypatch):
    database_session.close_database()
    monkeypatch.setattr(settings, "database_url", TEST_DATABASE_URL)
    test_app = FastAPI()

    @test_app.get("/database-session")
    def database_session_endpoint(db=Depends(database_session.get_db)):
        return {"driver": db.bind.url.drivername}

    with TestClient(test_app) as client:
        response = client.get("/database-session")

    database_session.close_database()
    assert response.status_code == 200
    assert response.json() == {"driver": "postgresql+psycopg"}


def test_database_dependency_rolls_back_before_closing_when_consumer_raises(monkeypatch):
    class FakeSession:
        rollback_called = False
        close_called = False

        def rollback(self):
            self.rollback_called = True

        def close(self):
            self.close_called = True

    session = FakeSession()
    monkeypatch.setattr(database_session, "get_session_factory", lambda: lambda: session)
    dependency = database_session.get_db()

    assert next(dependency) is session
    with pytest.raises(RuntimeError, match="request failed"):
        dependency.throw(RuntimeError("request failed"))

    assert session.rollback_called is True
    assert session.close_called is True


def test_database_url_loader_reads_project_dotenv_when_environment_is_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    (tmp_path / ".env").write_text(f"DATABASE_URL={TEST_DATABASE_URL}\n", encoding="utf-8")

    assert get_database_url_from_environment(tmp_path) == TEST_DATABASE_URL


def test_database_url_loader_preserves_environment_precedence(monkeypatch, tmp_path):
    environment_url = "postgresql+psycopg://environment:testing@localhost:5432/environment_test"
    (tmp_path / ".env").write_text(f"DATABASE_URL={TEST_DATABASE_URL}\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", environment_url)

    assert get_database_url_from_environment(tmp_path) == environment_url


def test_alembic_configuration_and_script_location_are_valid():
    project_root = Path(__file__).resolve().parents[1]
    config = Config(str(project_root / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)

    assert Path(scripts.dir).resolve() == project_root / "alembic"
    assert (project_root / "alembic" / "env.py").is_file()
