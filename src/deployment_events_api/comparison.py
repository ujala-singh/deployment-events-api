"""Pure logic for diffing two deployments of the same service.

Kept free of HTTP/FastAPI concerns so it is unit-testable in isolation; the
router layer is responsible for fetching deployments and raising errors.
"""

from __future__ import annotations

from .models import (
    ChangeSet,
    Deployment,
    DeploymentComparison,
    DeploymentStatus,
    PerformanceComparison,
    PerformanceVerdict,
    ServicePatterns,
    StatusTransition,
)

# Statuses whose `duration` reflects a real, completed run and can be compared.
MEASURABLE_STATUSES = frozenset(
    {DeploymentStatus.SUCCESS, DeploymentStatus.FAILED, DeploymentStatus.ROLLED_BACK}
)

# Statuses considered a "bad" release outcome for the pattern metrics.
BAD_RELEASE_STATUSES = frozenset({DeploymentStatus.FAILED, DeploymentStatus.ROLLED_BACK})


def _round1(value: float) -> float:
    """Round to one decimal place for human-readable percentages."""
    return round(value, 1)


def _build_changes(base: Deployment, target: Deployment) -> ChangeSet:
    """Diff the commit, status, and duration fields."""
    status_changed = base.status != target.status
    commit_changed = base.commit_sha != target.commit_sha
    duration_delta = target.duration - base.duration

    changed_fields: list[str] = []
    if commit_changed:
        changed_fields.append("commit_sha")
    if status_changed:
        changed_fields.append("status")
    if duration_delta != 0:
        changed_fields.append("duration")

    return ChangeSet(
        commit_changed=commit_changed,
        status_transition=StatusTransition(
            from_=base.status, to=target.status, changed=status_changed
        ),
        duration_delta=duration_delta,
        changed_fields=changed_fields,
    )


def _build_performance(base: Deployment, target: Deployment) -> PerformanceComparison:
    """Decide whether the target was faster, slower, or indeterminate.

    Returns an ``unknown`` verdict when either side lacks a measurable
    duration (``in_progress`` or ``cancelled``).
    """
    if base.status not in MEASURABLE_STATUSES or target.status not in MEASURABLE_STATUSES:
        return PerformanceComparison(
            verdict=PerformanceVerdict.UNKNOWN,
            duration_delta=None,
            pct_change=None,
            reason=(
                "Performance is indeterminate because at least one deployment is not a "
                f"completed run (base={base.status}, target={target.status})."
            ),
        )

    delta = target.duration - base.duration
    pct_change = _round1(delta / base.duration * 100) if base.duration else None

    if delta < 0:
        verdict = PerformanceVerdict.IMPROVED
        reason = f"Target is {abs(delta)}s faster than base."
    elif delta > 0:
        verdict = PerformanceVerdict.DEGRADED
        reason = f"Target is {delta}s slower than base."
    else:
        verdict = PerformanceVerdict.UNCHANGED
        reason = "Target and base have identical durations."

    return PerformanceComparison(
        verdict=verdict, duration_delta=delta, pct_change=pct_change, reason=reason
    )


def _build_patterns(
    base: Deployment,
    target: Deployment,
    service_deployments: list[Deployment],
    fleet_deployments: list[Deployment],
) -> ServicePatterns:
    """Compute service-level signals over the window between base and target.

    The window is the inclusive time range bounded by the two deployments'
    timestamps (order-independent), so it always contains at least base and
    target. Both percentages are scoped to that window:

    - ``bad_release_rate_pct``  = bad service deploys in window / service deploys in window
    - ``deployment_frequency_pct`` = service deploys in window / fleet deploys in window
    """
    low, high = sorted((base.timestamp, target.timestamp))

    def _in_window(deployment: Deployment) -> bool:
        return low <= deployment.timestamp <= high

    service_in_window = [d for d in service_deployments if _in_window(d)]
    fleet_in_window = [d for d in fleet_deployments if _in_window(d)]

    total = len(service_in_window)
    bad = sum(1 for d in service_in_window if d.status in BAD_RELEASE_STATUSES)

    bad_rate = _round1(bad / total * 100) if total else 0.0
    frequency = _round1(total / len(fleet_in_window) * 100) if fleet_in_window else 0.0

    return ServicePatterns(
        total_deployments=total,
        bad_release_rate_pct=bad_rate,
        deployment_frequency_pct=frequency,
    )


def compare_deployments(
    base: Deployment,
    target: Deployment,
    *,
    service_deployments: list[Deployment],
    fleet_deployments: list[Deployment],
) -> DeploymentComparison:
    """Produce a structured diff of two deployments of the same service.

    ``service_deployments`` is the full history for the service and
    ``fleet_deployments`` is every deployment across all services; the pattern
    metrics window both down to the time span between base and target.

    Callers must ensure ``base`` and ``target`` share a service; this function
    assumes that invariant and does not re-validate it.
    """
    return DeploymentComparison(
        service=base.service,
        base=base,
        target=target,
        changes=_build_changes(base, target),
        performance=_build_performance(base, target),
        service_patterns=_build_patterns(base, target, service_deployments, fleet_deployments),
    )
