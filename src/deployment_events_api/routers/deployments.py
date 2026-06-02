"""Routes for listing and retrieving deployment events."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import get_repository
from ..models import (
    Deployment,
    DeploymentList,
    DeploymentStatus,
    ErrorResponse,
)
from ..repository import DeploymentRepository

router = APIRouter(prefix="/deployments", tags=["deployments"])

RepositoryDep = Annotated[DeploymentRepository, Depends(get_repository)]


@router.get(
    "",
    response_model=DeploymentList,
    summary="List deployment events",
)
def list_deployments(
    repository: RepositoryDep,
    service: Annotated[
        str | None,
        Query(description="Filter by exact service name, e.g. `billing-api`."),
    ] = None,
    status_filter: Annotated[
        DeploymentStatus | None,
        Query(alias="status", description="Filter by deployment status."),
    ] = None,
) -> DeploymentList:
    """Return deployments (newest first), optionally filtered by service and status."""
    deployments = repository.list(service=service, status=status_filter)
    return DeploymentList(data=deployments, count=len(deployments))


@router.get(
    "/{deployment_id}",
    response_model=Deployment,
    summary="Get a single deployment event",
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
def get_deployment(deployment_id: str, repository: RepositoryDep) -> Deployment:
    """Return a single deployment by id, or 404 if it does not exist."""
    deployment = repository.get(deployment_id)
    if deployment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment '{deployment_id}' not found.",
        )
    return deployment
