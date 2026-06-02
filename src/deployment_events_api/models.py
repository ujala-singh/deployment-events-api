"""Pydantic schemas and enums for deployment events."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DeploymentStatus(str, Enum):
    """Lifecycle status of a deployment event."""

    SUCCESS = "success"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class Deployment(BaseModel):
    """A single deployment event."""

    id: str = Field(..., examples=["deploy_123"])
    service: str = Field(..., examples=["billing-api"])
    status: DeploymentStatus = Field(..., examples=[DeploymentStatus.FAILED])
    duration: int = Field(..., ge=0, description="Duration in seconds.", examples=[320])
    timestamp: datetime = Field(..., examples=["2025-04-28T14:32:00Z"])
    commit_sha: str = Field(..., examples=["abc123"])


class DeploymentList(BaseModel):
    """Envelope for a collection of deployments."""

    data: list[Deployment]
    count: int = Field(..., description="Number of deployments in `data`.")


class ErrorDetail(BaseModel):
    code: str = Field(..., examples=["not_found"])
    message: str = Field(..., examples=["Deployment 'deploy_999' not found."])


class ErrorResponse(BaseModel):
    """Consistent error envelope returned for all 4xx/5xx responses."""

    error: ErrorDetail
