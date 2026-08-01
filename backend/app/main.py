import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.analytics import router as analytics_router
from app.api.actions import router as actions_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.history import router as history_router
from app.api.metadata import router as metadata_router
from app.api.query import router as query_router
from app.api.reports import router as reports_router
from app.api.scenarios import router as scenarios_router
from app.api.settings import router as settings_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging


def _sanitized_validation_details(exc: RequestValidationError) -> list[dict]:
    """Validation input can contain credentials, so never reflect it to clients."""
    return [
        {key: error[key] for key in ("type", "loc", "msg") if key in error}
        for error in exc.errors()
    ]


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", uuid.uuid4().hex)


def _error_response(
    request: Request,
    *,
    code: str,
    message: str,
    status_code: int,
    details: dict | list | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )


def create_app() -> FastAPI:
    settings = get_settings()
    logger = configure_logging()
    app = FastAPI(
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url="/api/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "testserver"],
    )

    @app.middleware("http")
    async def add_request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = round((time.perf_counter() - started_at) * 1000)
            logger.info(
                "request_id=%s method=%s path=%s status=%s elapsed_ms=%s",
                request_id,
                request.method,
                request.url.path,
                500,
                elapsed_ms,
            )
            raise

        elapsed_ms = round((time.perf_counter() - started_at) * 1000)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_id=%s method=%s path=%s status=%s elapsed_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            request,
            code="VALIDATION_ERROR",
            message="Request validation failed",
            status_code=422,
            details=_sanitized_validation_details(exc),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled request error request_id=%s", _request_id(request))
        return _error_response(
            request,
            code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            status_code=500,
        )

    app.include_router(health_router)
    app.include_router(metadata_router)
    app.include_router(dashboard_router)
    app.include_router(analytics_router)
    app.include_router(actions_router)
    app.include_router(query_router)
    app.include_router(reports_router)
    app.include_router(scenarios_router)
    app.include_router(history_router)
    app.include_router(settings_router)
    return app
