from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import routes_analytics, routes_auth, routes_settings, routes_sync, routes_tags, routes_tickets
from app.auth import SESSION_COOKIE, verify_session_token
from app.config import get_settings
from app.db import SessionLocal
from app.scheduler import Scheduler
from app.settings_store import seed_defaults
from app.sync.manager import SyncManager
from app.trinity_client import TrinityClient

PUBLIC_PREFIXES = ("/api/v1/auth", "/api/v1/health")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if request.method != "OPTIONS" and path.startswith("/api/v1") and not path.startswith(PUBLIC_PREFIXES):
            settings = request.app.state.settings
            token = request.cookies.get(SESSION_COOKIE)
            email = verify_session_token(token, settings.session_secret)
            if not email:
                return JSONResponse({"detail": "Not authenticated"}, status_code=401)
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings

    client = TrinityClient(settings)
    await client.start()
    app.state.trinity_client = client

    async with SessionLocal() as session:
        await seed_defaults(session, settings)

    sync_manager = SyncManager(client, settings)
    app.state.sync_manager = sync_manager

    scheduler = Scheduler()
    scheduler.start(sync_manager, settings.poll_interval_minutes)
    app.state.scheduler = scheduler

    yield

    scheduler.shutdown()
    await client.stop()


app = FastAPI(title="QueueCortex API", lifespan=lifespan)

_settings = get_settings()

app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_auth.router, prefix="/api/v1")
app.include_router(routes_tickets.router, prefix="/api/v1")
app.include_router(routes_sync.router, prefix="/api/v1")
app.include_router(routes_tags.router, prefix="/api/v1")
app.include_router(routes_settings.router, prefix="/api/v1")
app.include_router(routes_analytics.router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
