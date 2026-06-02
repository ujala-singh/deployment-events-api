"""Sanity tests for the deployment events API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from deployment_events_api.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ui_shell_served_at_root(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Deployment Events" in resp.text


def test_static_assets_served(client: TestClient) -> None:
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200


def test_list_returns_all_seed_events(client: TestClient) -> None:
    resp = client.get("/deployments")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 45
    assert body["count"] == len(body["data"])


def test_list_is_sorted_newest_first(client: TestClient) -> None:
    data = client.get("/deployments").json()["data"]
    timestamps = [d["timestamp"] for d in data]
    assert timestamps == sorted(timestamps, reverse=True)


def test_filter_by_service(client: TestClient) -> None:
    resp = client.get("/deployments", params={"service": "billing-api"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data, "expected at least one billing-api deployment"
    assert all(d["service"] == "billing-api" for d in data)


def test_filter_by_status(client: TestClient) -> None:
    resp = client.get("/deployments", params={"status": "failed"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert all(d["status"] == "failed" for d in data)


def test_combined_filters(client: TestClient) -> None:
    resp = client.get(
        "/deployments", params={"service": "billing-api", "status": "failed"}
    )
    assert resp.status_code == 200
    assert all(
        d["service"] == "billing-api" and d["status"] == "failed"
        for d in resp.json()["data"]
    )


def test_invalid_status_returns_422(client: TestClient) -> None:
    resp = client.get("/deployments", params={"status": "exploded"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_get_single_deployment(client: TestClient) -> None:
    resp = client.get("/deployments/deploy_014")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "deploy_014"
    assert body["service"] == "billing-api"
    assert body["status"] == "failed"


def test_get_missing_deployment_returns_404(client: TestClient) -> None:
    resp = client.get("/deployments/deploy_999")
    assert resp.status_code == 404
    error = resp.json()["error"]
    assert error["code"] == "not_found"
    assert "deploy_999" in error["message"]
