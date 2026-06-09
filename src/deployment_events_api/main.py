"""Application factory, error handling, and entry point."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .models import ErrorResponse
from .repository import DeploymentRepository
from .routers import comparisons, deployments

_STATIC_DIR = Path(__file__).parent / "static"


def _error_body(code: str, message: str) -> dict:
    """Build the consistent error envelope shared by all handlers."""
    return ErrorResponse.model_validate({"error": {"code": code, "message": message}}).model_dump()


def _register_error_handlers(app: FastAPI) -> None:
    """Normalise every error response to a single `{ "error": {...} }` shape."""

    # 422 referenced as a literal — the named constant was renamed across
    # Starlette versions (UNPROCESSABLE_ENTITY → UNPROCESSABLE_CONTENT).
    _CODES_BY_STATUS = {
        status.HTTP_400_BAD_REQUEST: "bad_request",
        status.HTTP_404_NOT_FOUND: "not_found",
        422: "validation_error",
    }

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
        code = _CODES_BY_STATUS.get(exc.status_code, "error")
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(code, str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Surface the first validation problem in a readable sentence.
        first = exc.errors()[0]
        location = " → ".join(str(part) for part in first.get("loc", []))
        message = f"{first.get('msg', 'Invalid request.')} (at: {location})"
        return JSONResponse(
            status_code=422,
            content=_error_body("validation_error", message),
        )


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    app = FastAPI(
        title="Deployment Events API",
        version=__version__,
        description="Ingest and serve deployment event data.",
    )
    app.state.repository = DeploymentRepository.with_seed_data()

    _register_error_handlers(app)

    @app.get("/health", tags=["meta"], summary="Liveness check")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    app.include_router(deployments.router)
    app.include_router(comparisons.router)

    # Serve the browser UI: assets under /static, the SPA shell at /.
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def ui() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    # Client-routed compare view; served by the same SPA shell.
    @app.get("/d/compare", include_in_schema=False)
    def ui_compare() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    return app


app = create_app()


def main() -> None:
    """Run the development server via `uv run deployment-events-api`."""
    import uvicorn

    uvicorn.run(
        "deployment_events_api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
