"""Load mock deployment events used to seed the in-memory store.

The seed events live in ``data/seed_deployments.json`` so the fixture data is
editable without touching code. The file ships with the package and is read
once at runtime.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .models import Deployment

_SEED_FILE = Path(__file__).parent / "data" / "seed_deployments.json"


@lru_cache(maxsize=1)
def _raw_events() -> tuple[dict, ...]:
    """Read and cache the raw seed records from disk."""
    with _SEED_FILE.open(encoding="utf-8") as fh:
        records = json.load(fh)
    return tuple(records)


def seed_deployments() -> list[Deployment]:
    """Return a fresh list of seed deployments parsed into models."""
    return [Deployment.model_validate(event) for event in _raw_events()]
