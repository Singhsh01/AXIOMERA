"""Test harness: a dedicated PostgreSQL database (pgvector required), n8n disabled so the
API's documented fallback paths run inline and deterministically."""
from __future__ import annotations

import os
import tempfile

os.environ.setdefault("AXIOMERA_DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/axiomera_test")
os.environ["AXIOMERA_N8N_ENABLED"] = "false"
os.environ["AXIOMERA_LLM_PROVIDER"] = "fixture"
os.environ["AXIOMERA_STORAGE_DIR"] = tempfile.mkdtemp(prefix="axiomera-test-")
os.environ["AXIOMERA_RATE_LIMIT_PER_MINUTE"] = "100000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import Base, reset_engine, session_factory  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def database():
    engine = reset_engine(os.environ["AXIOMERA_DATABASE_URL"])
    with engine.begin() as c:
        c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public; CREATE EXTENSION IF NOT EXISTS vector"))
    import app.models  # noqa: F401

    Base.metadata.create_all(engine)
    from app.seed import seed

    seed()
    yield engine


@pytest.fixture()
def db():
    s = session_factory()()
    yield s
    s.rollback()
    s.close()


@pytest.fixture(scope="session")
def client(database):
    from app.main import app

    return TestClient(app)


def _login(client, email):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "axiomera-demo"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="session")
def ops_h(client):
    return _login(client, "ops@axiomera.dev")


@pytest.fixture(scope="session")
def approver_h(client):
    return _login(client, "approver@axiomera.dev")


@pytest.fixture(scope="session")
def admin_h(client):
    return _login(client, "admin@axiomera.dev")


@pytest.fixture(scope="session")
def reviewer_h(client):
    return _login(client, "reviewer@axiomera.dev")


@pytest.fixture(scope="session")
def viewer_h(client):
    return _login(client, "viewer@axiomera.dev")


@pytest.fixture()
def svc_h():
    """Headers n8n sends."""
    return {"X-Axiomera-Service-Token": "dev-service-token", "X-N8N-Execution-Id": "test-exec", "X-Axiomera-Workflow": "A"}


@pytest.fixture(scope="session")
def workspace_id(database):
    from app.models import Workspace

    s = session_factory()()
    try:
        return s.query(Workspace).first().id
    finally:
        s.close()
