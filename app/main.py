import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)
log = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        structlog.contextvars.clear_contextvars()
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    for p in (
        settings.STORAGE_ROOT,
        settings.cars_upload_dir,
        settings.leads_upload_dir,
        settings.excel_upload_dir,
        settings.EXCEL_INBOX_DIR,
    ):
        Path(p).mkdir(parents=True, exist_ok=True)
    log.info("startup", app=settings.APP_NAME, env=settings.APP_ENV)
    yield
    log.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
        openapi_tags=[
            {"name": "public", "description": "Public endpoints"},
            {"name": "auth", "description": "Authentication"},
            {"name": "admin", "description": "Admin API"},
        ],
    )
    app.add_middleware(RequestIDMiddleware)

    # Static & media mounts
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Public media: only cars + leads (NOT excel — admin only via dedicated route)
    settings.cars_upload_dir.mkdir(parents=True, exist_ok=True)
    settings.leads_upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/media/cars",
        StaticFiles(directory=settings.cars_upload_dir),
        name="media_cars",
    )
    app.mount(
        "/media/leads",
        StaticFiles(directory=settings.leads_upload_dir),
        name="media_leads",
    )

    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    app.state.templates = templates

    # Routers
    from app.admin import cars as admin_cars
    from app.admin import dashboard as admin_dashboard
    from app.admin import excel as admin_excel
    from app.admin import leads as admin_leads
    from app.admin import logs as admin_logs
    from app.admin import media as admin_media
    from app.admin import settings as admin_settings
    from app.api import auth as api_auth
    from app.api import cars as api_cars
    from app.api import excel as api_excel
    from app.api import leads as api_leads
    from app.api import notifications as api_notifications
    from app.public import routes as public_routes

    app.include_router(api_auth.router)
    app.include_router(api_cars.router)
    app.include_router(api_leads.router)
    app.include_router(api_excel.router)
    app.include_router(api_notifications.router)

    app.include_router(admin_dashboard.router)
    app.include_router(admin_cars.router)
    app.include_router(admin_excel.router)
    app.include_router(admin_leads.router)
    app.include_router(admin_logs.router)
    app.include_router(admin_media.router)
    app.include_router(admin_settings.router)

    app.include_router(public_routes.router)

    @app.exception_handler(StarletteHTTPException)
    async def http_exc_handler(request: Request, exc: StarletteHTTPException):
        if request.url.path.startswith("/api"):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": {
                        "code": f"http_{exc.status_code}",
                        "message": exc.detail,
                        "details": {},
                    }
                },
            )
        if request.url.path.startswith("/admin"):
            return templates.TemplateResponse(
                "admin/error.html",
                {
                    "request": request,
                    "status_code": exc.status_code,
                    "message": exc.detail,
                    "request_id": getattr(request.state, "request_id", ""),
                },
                status_code=exc.status_code,
            )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exc_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Invalid input",
                    "details": exc.errors(),
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exc_handler(request: Request, exc: Exception):
        log.exception("unhandled", path=request.url.path)
        if request.url.path.startswith("/api"):
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "internal_error",
                        "message": "Internal server error",
                        "details": {"request_id": getattr(request.state, "request_id", "")},
                    }
                },
            )
        return templates.TemplateResponse(
            "admin/error.html",
            {
                "request": request,
                "status_code": 500,
                "message": "Internal server error",
                "request_id": getattr(request.state, "request_id", ""),
            },
            status_code=500,
        )

    @app.get("/healthz", tags=["public"])
    async def healthz():
        return {"status": "ok"}

    return app


app = create_app()
