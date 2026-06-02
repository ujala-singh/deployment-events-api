"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from .repository import DeploymentRepository


def get_repository(request: Request) -> DeploymentRepository:
    """Return the process-wide repository stored on app state.

    Centralising access here makes the repository trivial to override in
    tests (via ``app.dependency_overrides``).
    """
    return request.app.state.repository
