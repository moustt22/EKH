import time
from collections import defaultdict
from threading import Lock

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.workflows.tracing import configure_tracing


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_runtime()
    configure_tracing()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    request_log: dict[tuple[str, str], list[float]] = defaultdict(list)
    request_lock = Lock()

    @app.middleware("http")
    async def throttle_requests(request: Request, call_next):
        if not settings.rate_limit_enabled:
            return await call_next(request)
        path = request.url.path
        if path.startswith("/auth/login"):
            limit = settings.login_rate_limit
        elif path.startswith(("/conversations", "/search", "/documents")):
            limit = settings.api_rate_limit
        else:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        key = (path.split("/", 2)[1] or "root", client)
        with request_lock:
            recent = [item for item in request_log[key] if now - item < settings.rate_limit_window_seconds]
            if len(recent) >= limit:
                request_log[key] = recent
                return JSONResponse(status_code=429, content={"detail": "Too many requests; try again later"})
            recent.append(now)
            request_log[key] = recent
        return await call_next(request)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()
