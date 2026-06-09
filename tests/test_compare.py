"""Tests for the /compare endpoint and the pure comparison logic."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from deployment_events_api.comparison import compare_deployments
from deployment_events_api.main import create_app
from deployment_events_api.models import Deployment, DeploymentStatus


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _deployment(
    deployment_id: str,
    *,
    service: str = "billing-api",
    status: DeploymentStatus = DeploymentStatus.SUCCESS,
    duration: int = 100,
    commit_sha: str = "aaa111",
    day: int = 1,
) -> Deployment:
    return Deployment(
        id=deployment_id,
        service=service,
        status=status,
        duration=duration,
        timestamp=datetime(2025, 5, day, 12, 0, 0),
        commit_sha=commit_sha,
    )


# --- Pure logic ------------------------------------------------------------


def test_degraded_when_target_slower() -> None:
    base = _deployment("d1", duration=100, status=DeploymentStatus.SUCCESS, commit_sha="aaa")
    target = _deployment("d2", duration=150, status=DeploymentStatus.FAILED, commit_sha="bbb")

    result = compare_deployments(
        base, target, service_deployments=[base, target], fleet_deployments=[base, target]
    )

    assert result.performance.verdict == "degraded"
    assert result.performance.duration_delta == 50
    assert result.performance.pct_change == 50.0
    assert result.changes.commit_changed is True
    assert set(result.changes.changed_fields) == {"commit_sha", "status", "duration"}
    assert result.changes.status_transition.changed is True


def test_improved_when_target_faster() -> None:
    base = _deployment("d1", duration=200)
    target = _deployment("d2", duration=120)

    result = compare_deployments(
        base, target, service_deployments=[base, target], fleet_deployments=[base, target]
    )

    assert result.performance.verdict == "improved"
    assert result.performance.duration_delta == -80


def test_unchanged_when_equal_duration() -> None:
    base = _deployment("d1", duration=100)
    target = _deployment("d2", duration=100, commit_sha="bbb")

    result = compare_deployments(
        base, target, service_deployments=[base, target], fleet_deployments=[base, target]
    )

    assert result.performance.verdict == "unchanged"
    assert "duration" not in result.changes.changed_fields


def test_unknown_when_in_progress() -> None:
    base = _deployment("d1", status=DeploymentStatus.IN_PROGRESS, duration=0)
    target = _deployment("d2", status=DeploymentStatus.SUCCESS, duration=100)

    result = compare_deployments(
        base, target, service_deployments=[base, target], fleet_deployments=[base, target]
    )

    assert result.performance.verdict == "unknown"
    assert result.performance.duration_delta is None
    assert result.performance.pct_change is None


def test_unknown_when_cancelled() -> None:
    base = _deployment("d1", status=DeploymentStatus.SUCCESS, duration=100)
    target = _deployment("d2", status=DeploymentStatus.CANCELLED, duration=0)

    result = compare_deployments(
        base, target, service_deployments=[base, target], fleet_deployments=[base, target]
    )

    assert result.performance.verdict == "unknown"


def test_pct_change_null_when_base_zero_but_measurable() -> None:
    # Both terminal, but base duration is 0 -> percentage is undefined, not a crash.
    base = _deployment("d1", status=DeploymentStatus.FAILED, duration=0)
    target = _deployment("d2", status=DeploymentStatus.SUCCESS, duration=100)

    result = compare_deployments(
        base, target, service_deployments=[base, target], fleet_deployments=[base, target]
    )

    assert result.performance.verdict == "degraded"
    assert result.performance.duration_delta == 100
    assert result.performance.pct_change is None


def test_service_patterns_windowed() -> None:
    # Window is the inclusive span [day 10, day 16]; deploys outside are ignored.
    base = _deployment("base", day=10, status=DeploymentStatus.SUCCESS)
    target = _deployment("target", day=16, status=DeploymentStatus.FAILED)

    service_deployments = [
        _deployment("before", day=5, status=DeploymentStatus.ROLLED_BACK),  # outside
        base,  # in window
        _deployment("mid", day=13, status=DeploymentStatus.ROLLED_BACK),  # in window (bad)
        target,  # in window (bad)
        _deployment("after", day=20, status=DeploymentStatus.SUCCESS),  # outside
    ]
    fleet_deployments = [
        *service_deployments,
        _deployment("f1", service="auth-service", day=12),  # in window
        _deployment("f2", service="auth-service", day=14),  # in window
        _deployment("f3", service="auth-service", day=25),  # outside
    ]

    result = compare_deployments(
        base,
        target,
        service_deployments=service_deployments,
        fleet_deployments=fleet_deployments,
    )

    # In window for the service: base, mid, target -> 3 deploys, 2 of them bad.
    assert result.service_patterns.total_deployments == 3
    assert result.service_patterns.bad_release_rate_pct == 66.7
    # Fleet in window: 3 service + f1 + f2 = 5 -> 3/5 = 60%.
    assert result.service_patterns.deployment_frequency_pct == 60.0


# --- Endpoint --------------------------------------------------------------


def test_compare_happy_path(client: TestClient) -> None:
    # deploy_009 (success, billing-api) vs deploy_014 (failed, billing-api).
    resp = client.get("/compare", params={"from": "deploy_009", "to": "deploy_014"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "billing-api"
    assert body["base"]["id"] == "deploy_009"
    assert body["target"]["id"] == "deploy_014"
    assert body["changes"]["status_transition"]["from"] == "success"
    assert body["changes"]["status_transition"]["to"] == "failed"
    assert body["performance"]["verdict"] in {"improved", "degraded", "unchanged"}
    assert body["service_patterns"]["total_deployments"] >= 1


def test_compare_unknown_id_returns_404(client: TestClient) -> None:
    resp = client.get("/compare", params={"from": "deploy_999", "to": "deploy_014"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
    assert "deploy_999" in resp.json()["error"]["message"]


def test_compare_different_services_returns_400(client: TestClient) -> None:
    # deploy_009 is billing-api, deploy_002 is auth-service.
    resp = client.get("/compare", params={"from": "deploy_009", "to": "deploy_002"})
    assert resp.status_code == 400
    error = resp.json()["error"]
    assert error["code"] == "bad_request"
    assert "different services" in error["message"]


def test_compare_self_returns_400(client: TestClient) -> None:
    resp = client.get("/compare", params={"from": "deploy_009", "to": "deploy_009"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "bad_request"
    assert "itself" in resp.json()["error"]["message"]


def test_compare_missing_param_returns_422(client: TestClient) -> None:
    resp = client.get("/compare", params={"from": "deploy_009"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_compare_ui_shell_served(client: TestClient) -> None:
    resp = client.get("/d/compare")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Deployment Events" in resp.text
