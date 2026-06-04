import time
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from api.root_router import root_router
from app.core.config.config import loader
from app.core.db.schema import init_schema
from app.core.db.session import dispose_engines, init_engines
from app.core.exception.error_base import CustomException
from app.core.exception.exception_handlers import (
    custom_exception_handler,
    validation_exception_handler,
)
from app.core.fastapi.middlewares.sqlalchemy import SQLAlchemyMiddleware


class LoginRateLimitMiddleware(BaseHTTPMiddleware):
    """5 login attempts per IP per 60 s to limit brute-force."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_attempts: int = 5,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self._max = max_attempts
        self._window = window_seconds
        self._attempts: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path.endswith("/auth/login") and request.method == "POST":
            # In-process limiter — resets on restart and does not coordinate across
            # workers. Keep WORKERS=1 in prod or move to Redis.
            xff = request.headers.get("x-forwarded-for")
            if xff:
                ip = xff.split(",")[-1].strip() or "unknown"
            else:
                ip = (request.client.host if request.client else None) or "unknown"
            now = time.time()
            window = [t for t in self._attempts.get(ip, []) if now - t < self._window]
            if len(window) >= self._max:
                return JSONResponse(
                    {"error": {"code": "TOO_MANY_REQUESTS", "message": "Too many login attempts"}},  # noqa: E501
                    status_code=429,
                )
            window.append(now)
            self._attempts[ip] = window
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Local/test only — in prod the gateway sets these headers."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        return response


class GatewaySharedSecretMiddleware(BaseHTTPMiddleware):
    """Reject requests that did not traverse the gateway.

    The gateway attaches `X-Gateway-Auth: <secret>` to every downstream call
    via GatewayHopHeaderFilter; the backend timing-safe compares it against
    `GATEWAY_SHARED_SECRET`. This is a second line of defense behind the
    NetworkPolicy. Empty secret disables enforcement — must be set in prod.

    Bypass paths:
      * `/healthz`              — k8s probes (no client to set the header).
      * `/.well-known/jwks.json` — the gateway's NimbusReactiveJwtDecoder
                                   fetches this directly without going through
                                   the gateway chain, so no hop header is
                                   stamped. The endpoint exposes only the
                                   public key; NetworkPolicy continues to
                                   restrict who can reach it.
    """

    PROBE_PATHS = ("/healthz", "/.well-known/jwks.json")
    HEADER = "X-Gateway-Auth"

    def __init__(self, app: ASGIApp, *, expected_secret: str) -> None:
        super().__init__(app)
        self._expected = expected_secret

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self._expected:
            return await call_next(request)
        if request.url.path in self.PROBE_PATHS:
            return await call_next(request)
        supplied = request.headers.get(self.HEADER, "")
        if not _constant_time_equal(supplied, self._expected):
            return JSONResponse(
                {"error": {"code": "GATEWAY_HOP_MISSING",
                           "message": "Request must traverse the gateway."}},
                status_code=401,
            )
        return await call_next(request)


def _constant_time_equal(a: str, b: str) -> bool:
    """Constant-time string compare to defend against timing oracles."""
    import hmac
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncGenerator[None]:
    init_engines(database_url=loader.config.DATABASE_URL, echo=loader.config.DEBUG)
    await init_schema()
    try:
        yield
    finally:
        await dispose_engines()


def init_middleware() -> list[Middleware]:
    """Middleware order: outermost first (first request, last response).

    In prod the gateway handles CORS / security headers / rate limit; the
    backend only verifies the gateway-hop secret.
    """
    cfg = loader.config
    middleware: list[Middleware] = []

    if cfg.is_prod:
        middleware.append(
            Middleware(
                GatewaySharedSecretMiddleware,
                expected_secret=cfg.GATEWAY_SHARED_SECRET,
            ),
        )
    else:
        middleware.extend(
            [
                Middleware(
                    CORSMiddleware,
                    allow_origins=cfg.cors_origins_list,
                    allow_credentials=True,
                    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                    allow_headers=["Authorization", "Content-Type"],
                ),
                Middleware(SecurityHeadersMiddleware),
                Middleware(LoginRateLimitMiddleware),
            ]
        )
    middleware.append(Middleware(SQLAlchemyMiddleware))
    return middleware


def init_app() -> FastAPI:
    is_prod = loader.config.is_prod
    application = FastAPI(
        lifespan=lifespan,
        title="blog_be",
        description="Backend for blog_ui (Next.js)",
        version="0.1.0",
        docs_url=None if is_prod else "/swagger_ui",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
        middleware=init_middleware(),
    )
    application.include_router(root_router)
    application.add_exception_handler(CustomException, custom_exception_handler)
    application.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )
    return application


app = init_app()
