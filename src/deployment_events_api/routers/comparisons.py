"""Route for comparing two deployments of the same service."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..comparison import compare_deployments
from ..dependencies import get_repository
from ..models import Deployment, DeploymentComparison, ErrorResponse
from ..repository import DeploymentRepository

router = APIRouter(prefix="/compare", tags=["comparisons"])

RepositoryDep = Annotated[DeploymentRepository, Depends(get_repository)]


def _require_deployment(repository: DeploymentRepository, deployment_id: str) -> Deployment:
    """Fetch a deployment or raise 404 if it does not exist."""
    deployment = repository.get(deployment_id)
    if deployment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment '{deployment_id}' not found.",
        )
    return deployment


@router.get(
    "",
    response_model=DeploymentComparison,
    summary="Compare two deployments of the same service",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def compare(
    repository: RepositoryDep,
    from_: Annotated[
        str,
        Query(alias="from", description="ID of the base (earlier) deployment."),
    ],
    to: Annotated[
        str,
        Query(description="ID of the target (later) deployment."),
    ],
) -> DeploymentComparison:
    """Diff two deployments and report what changed, performance, and patterns.

    Both deployments must exist (404 otherwise) and belong to the same service
    (400 otherwise). Comparing a deployment with itself is rejected (400).
    """
    base = _require_deployment(repository, from_)
    target = _require_deployment(repository, to)

    if from_ == to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot compare a deployment with itself.",
        )

    if base.service != target.service:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cannot compare deployments from different services "
                f"({base.service} vs {target.service})."
            ),
        )

    service_deployments = repository.list(service=base.service)
    fleet_deployments = repository.list()

    return compare_deployments(
        base,
        target,
        service_deployments=service_deployments,
        fleet_deployments=fleet_deployments,
    )
