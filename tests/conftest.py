"""Test environment setup.

Runs before any `app.*` module is imported by a test file, so it forces a
deterministic, isolated environment: no OpenAI calls (tests never spend API
credits or depend on network), and an isolated temp SQLite DB (never touches
local.db or a real Postgres instance).
"""

import os
import tempfile

os.environ["AI_PROVIDER"] = "simulated"
os.environ["OPENAI_API_KEY"] = ""

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

import pytest
from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    init_db()
    yield
    os.close(_db_fd)
    os.remove(_db_path)


@pytest.fixture
def client():
    return TestClient(app)
