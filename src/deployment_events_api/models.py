"""Pydantic schemas and enums for deployment events."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DeploymentStatus(StrEnum):
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


class PerformanceVerdict(StrEnum):
    """Direction of a performance change between two deployments."""

    IMPROVED = "improved"
    DEGRADED = "degraded"
    UNCHANGED = "unchanged"
    UNKNOWN = "unknown"


class StatusTransition(BaseModel):
    """Status change from a base deployment to a target deployment."""

    # ``from`` is a Python keyword, so the field is ``from_`` exposed via alias.
    model_config = ConfigDict(populate_by_name=True)

    from_: DeploymentStatus = Field(..., alias="from", examples=[DeploymentStatus.SUCCESS])
    to: DeploymentStatus = Field(..., examples=[DeploymentStatus.FAILED])
    changed: bool = Field(..., description="True when the status differs between the two.")


class ChangeSet(BaseModel):
    """What changed between the base and target deployment."""

    commit_changed: bool
    status_transition: StatusTransition
    duration_delta: int = Field(..., description="target.duration - base.duration, in seconds.")
    changed_fields: list[str] = Field(
        ..., description="Subset of {commit_sha, status, duration} that differ."
    )


class PerformanceComparison(BaseModel):
    """Whether the target deployment was faster or slower than the base.

    ``verdict`` is ``unknown`` when either deployment lacks a measurable
    duration (e.g. ``in_progress`` or ``cancelled``).
    """

    verdict: PerformanceVerdict
    duration_delta: int | None = Field(
        None, description="Signed seconds; null when verdict is unknown."
    )
    pct_change: float | None = Field(
        None, description="Percent change vs base; null when base is 0 or verdict unknown."
    )
    reason: str


class ServicePatterns(BaseModel):
    """Service-level signals over the time window between the two deployments.

    The window is the inclusive span bounded by the base and target timestamps.
    """

    total_deployments: int = Field(
        ..., description="The service's deployments within the base..target window (inclusive)."
    )
    bad_release_rate_pct: float = Field(
        ...,
        description="(failed + rolled_back) / service deployments in the window, as a percent.",
    )
    deployment_frequency_pct: float = Field(
        ...,
        description="Service deployments in the window / fleet deployments in the window, percent.",
    )


class DeploymentComparison(BaseModel):
    """Structured diff of two deployments belonging to the same service."""

    service: str
    base: Deployment
    target: Deployment
    changes: ChangeSet
    performance: PerformanceComparison
    service_patterns: ServicePatterns


class ErrorDetail(BaseModel):
    code: str = Field(..., examples=["not_found"])
    message: str = Field(..., examples=["Deployment 'deploy_999' not found."])


class ErrorResponse(BaseModel):
    """Consistent error envelope returned for all 4xx/5xx responses."""

    error: ErrorDetail
