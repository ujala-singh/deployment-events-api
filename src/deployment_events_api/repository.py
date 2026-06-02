"""In-memory storage and querying for deployment events.

The repository is the single seam between the API layer and the data store.
Swapping in SQLite/Postgres later means reimplementing this class only.
"""

from __future__ import annotations

from .models import Deployment, DeploymentStatus
from .seed import seed_deployments


class DeploymentRepository:
    """Holds deployments in memory, keyed by id for O(1) lookups."""

    def __init__(self, deployments: list[Deployment] | None = None) -> None:
        self._by_id: dict[str, Deployment] = {}
        for deployment in deployments or []:
            self._by_id[deployment.id] = deployment

    @classmethod
    def with_seed_data(cls) -> DeploymentRepository:
        return cls(seed_deployments())

    def get(self, deployment_id: str) -> Deployment | None:
        """Return a single deployment by id, or None if absent."""
        return self._by_id.get(deployment_id)

    def list(
        self,
        *,
        service: str | None = None,
        status: DeploymentStatus | None = None,
    ) -> list[Deployment]:
        """Return deployments matching the given filters, newest first.

        Filters are ANDed together; passing none returns every deployment.
        """
        results = list(self._by_id.values())

        if service is not None:
            results = [d for d in results if d.service == service]
        if status is not None:
            results = [d for d in results if d.status == status]

        results.sort(key=lambda d: d.timestamp, reverse=True)
        return results
