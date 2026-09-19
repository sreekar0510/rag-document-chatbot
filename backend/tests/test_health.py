"""Tests for the health endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "timestamp" in body


def test_health_response_has_request_id_header() -> None:
    response = client.get("/api/health")
    assert "x-request-id" in response.headers


def test_health_accepts_custom_request_id() -> None:
    custom_id = "test-request-id-123"
    response = client.get("/api/health", headers={"X-Request-ID": custom_id})
    assert response.headers.get("x-request-id") == custom_id
