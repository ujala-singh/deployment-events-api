# deployment-events-api

A lightweight REST API for ingesting and serving deployment event data, with
filtering, in-memory storage, and mock seed data across multiple services and
statuses.

Built with **FastAPI** and managed with **[uv](https://docs.astral.sh/uv/)**.

## Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (`brew install uv`)

uv manages the Python toolchain itself — it will fetch a compatible Python
(3.11+) automatically, so nothing else needs to be installed.

## Run it (under 2 minutes)

```bash
uv sync                                              # install dependencies
uv run uvicorn deployment_events_api.main:app --reload
```

The API is now serving on **http://127.0.0.1:8000**, pre-seeded with 45
deployment events.

- **Web UI**: http://127.0.0.1:8000/ — lists all deployments with service/status
  filters; click any deployment ID to view its details.
- **Compare view**: http://127.0.0.1:8000/d/compare — pick two deployments of the
  same service and see a structured diff. Deep-linkable, e.g.
  `/d/compare?from=deploy_009&to=deploy_014`.
- Interactive docs (Swagger UI): http://127.0.0.1:8000/docs
- OpenAPI schema: http://127.0.0.1:8000/openapi.json

The UI is a single static page (no build step) served by the same FastAPI app;
it talks to the JSON API below via `fetch`, so one command runs everything.

### Alternative: plain `venv` + `pip` (without uv)

Prefer the standard toolchain? Use a Python **3.11+** interpreter (the code uses
`StrEnum` and modern typing):

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# Install the app (runtime deps) — plus dev tools for tests/lint
pip install -e .
pip install pytest httpx ruff

# Run the server
uvicorn deployment_events_api.main:app --reload
```

> `uv` remains the recommended path: it provisions the right Python
> automatically and installs from the pinned `uv.lock` for reproducible builds.

## Run the tests

```bash
uv run pytest          # or just `pytest` with the venv activated
```

Linting and formatting use [ruff](https://docs.astral.sh/ruff/):

```bash
uv run ruff check .            # lint
uv run ruff format --check .   # verify formatting
```

## Endpoints

| Method | Path                  | Description                                   |
| ------ | --------------------- | --------------------------------------------- |
| `GET`  | `/health`             | Liveness check.                               |
| `GET`  | `/deployments`        | List deployments (filterable, newest first).  |
| `GET`  | `/deployments/{id}`   | Fetch a single deployment by id.              |
| `GET`  | `/compare`            | Diff two deployments of the same service.     |

### `GET /deployments`

Query parameters (both optional, ANDed together):

| Param     | Example       | Notes                                                                  |
| --------- | ------------- | ---------------------------------------------------------------------- |
| `service` | `billing-api` | Exact service-name match.                                              |
| `status`  | `failed`      | One of `success`, `failed`, `in_progress`, `cancelled`, `rolled_back`. |

```bash
curl "http://127.0.0.1:8000/deployments?service=billing-api&status=failed"
```

```json
{
  "data": [
    {
      "id": "deploy_038",
      "service": "billing-api",
      "status": "failed",
      "duration": 305,
      "timestamp": "2025-05-14T17:09:00Z",
      "commit_sha": "f6adf6e"
    },
    {
      "id": "deploy_014",
      "service": "billing-api",
      "status": "failed",
      "duration": 320,
      "timestamp": "2025-04-16T14:32:00Z",
      "commit_sha": "7e25d6e"
    }
  ],
  "count": 2
}
```

### `GET /deployments/{id}`

```bash
curl http://127.0.0.1:8000/deployments/deploy_001
```

```json
{
  "id": "deploy_001",
  "service": "billing-api",
  "status": "success",
  "duration": 142,
  "timestamp": "2025-04-01T09:14:00Z",
  "commit_sha": "a1b2c3d"
}
```

### `GET /compare`

Diffs two deployments **of the same service**. Both query params are required.

| Param  | Example      | Notes                          |
| ------ | ------------ | ------------------------------ |
| `from` | `deploy_009` | Base (earlier) deployment id.  |
| `to`   | `deploy_014` | Target (later) deployment id.  |

```bash
curl "http://127.0.0.1:8000/compare?from=deploy_009&to=deploy_014"
```

Returns what changed, a performance verdict, and service patterns scoped to the
time window **between** the two deployments:

```json
{
  "service": "billing-api",
  "base":   { "id": "deploy_009", "status": "success", "duration": 134, "...": "..." },
  "target": { "id": "deploy_014", "status": "failed",  "duration": 320, "...": "..." },
  "changes": {
    "commit_changed": true,
    "status_transition": { "from": "success", "to": "failed", "changed": true },
    "duration_delta": 186,
    "changed_fields": ["commit_sha", "status", "duration"]
  },
  "performance": {
    "verdict": "degraded",
    "duration_delta": 186,
    "pct_change": 138.8,
    "reason": "Target is 186s slower than base."
  },
  "service_patterns": {
    "total_deployments": 2,
    "bad_release_rate_pct": 50.0,
    "deployment_frequency_pct": 33.3
  }
}
```

- **`performance.verdict`** is `improved` / `degraded` / `unchanged`, or `unknown`
  when either deployment is `in_progress`/`cancelled` (no measurable duration).
- **`service_patterns`** count only deployments in the inclusive window between
  `from` and `to`; `deployment_frequency_pct` is the service's share of *fleet*
  deployments in that same window.
- Comparing different services, or a deployment with itself, returns `400`.

## Responses & errors

- List responses are wrapped in an envelope: `{ "data": [...], "count": N }`.
- A single deployment is returned as the bare resource object.
- Errors share one consistent shape:

  ```json
  { "error": { "code": "not_found", "message": "Deployment 'deploy_999' not found." } }
  ```

| Situation                           | Status | `error.code`       |
| ----------------------------------- | ------ | ------------------ |
| Resource fetched / list returned    | `200`  | —                  |
| Invalid combination (diff service)  | `400`  | `bad_request`      |
| Unknown deployment id               | `404`  | `not_found`        |
| Invalid query value (e.g. `status`) | `422`  | `validation_error` |

## Project layout

```
src/deployment_events_api/
  main.py            # app factory, error handlers, static UI mount, entry point
  models.py          # Pydantic schemas + status enum
  repository.py      # in-memory store + filtering/query logic
  comparison.py      # pure diff logic backing /compare
  seed.py            # loads seed events from data/ at runtime
  dependencies.py    # repository injection
  data/
    seed_deployments.json  # 45 mock deployment events (editable, no code change)
  routers/
    deployments.py   # /deployments routes
    comparisons.py   # /compare route
  static/            # browser UI: list, detail, and /d/compare views
tests/
  test_deployments.py
  test_compare.py
```

The `DeploymentRepository` is the single seam between the API and storage —
swapping the in-memory store for SQLite/Postgres later means reimplementing
that one class, nothing in the route layer.
