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
- Interactive docs (Swagger UI): http://127.0.0.1:8000/docs
- OpenAPI schema: http://127.0.0.1:8000/openapi.json

The UI is a single static page (no build step) served by the same FastAPI app;
it talks to the JSON API below via `fetch`, so one command runs everything.

## Run the tests

```bash
uv run pytest
```

## Endpoints

| Method | Path                  | Description                                   |
| ------ | --------------------- | --------------------------------------------- |
| `GET`  | `/health`             | Liveness check.                               |
| `GET`  | `/deployments`        | List deployments (filterable, newest first).  |
| `GET`  | `/deployments/{id}`   | Fetch a single deployment by id.              |

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
      "id": "deploy_014",
      "service": "billing-api",
      "status": "failed",
      "duration": 320,
      "timestamp": "2025-04-16T14:32:00Z",
      "commit_sha": "7e25d6e"
    }
  ],
  "count": 1
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
| Unknown deployment id               | `404`  | `not_found`        |
| Invalid query value (e.g. `status`) | `422`  | `validation_error` |

## Project layout

```
src/deployment_events_api/
  main.py            # app factory, error handlers, static UI mount, entry point
  models.py          # Pydantic schemas + status enum
  repository.py      # in-memory store + filtering/query logic
  seed.py            # loads seed events from data/ at runtime
  dependencies.py    # repository injection
  data/
    seed_deployments.json  # 45 mock deployment events (editable, no code change)
  routers/
    deployments.py   # /deployments routes
  static/            # browser UI (index.html, app.js, styles.css)
tests/
  test_deployments.py
```

The `DeploymentRepository` is the single seam between the API and storage —
swapping the in-memory store for SQLite/Postgres later means reimplementing
that one class, nothing in the route layer.
