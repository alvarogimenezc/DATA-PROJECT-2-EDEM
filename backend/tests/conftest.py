"""Pytest fixtures — force in-memory local store and provide a TestClient."""

import os

import pytest

# Ensure the app boots in local mode before any import of cloudrisk_api.main
os.environ.setdefault("USE_LOCAL_STORE", "1")
os.environ.setdefault("SECRET_KEY", "test-secret-key")


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from cloudrisk_api.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def registered_user(client):
    """Register a fresh user and return (email, password, token)."""
    import uuid

    email = f"tester-{uuid.uuid4().hex[:8]}@example.com"
    password = "s3cret-pass"
    resp = client.post(
        "/api/v1/users/register",
        json={"name": "Tester", "email": email, "password": password},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"email": email, "password": password, "token": token}
