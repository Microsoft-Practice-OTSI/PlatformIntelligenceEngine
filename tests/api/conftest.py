"""Pytest fixtures for FastAPI TestClient and preloaded repository."""

import pytest
from starlette.testclient import TestClient

from pie.api.app import app
from pie.discovery.repository import get_repository


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Provide initialized TestClient for the FastAPI app."""
    repo = get_repository()
    repo.preload_defaults()
    return TestClient(app)
