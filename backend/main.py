from contextlib import asynccontextmanager
import os
import secrets
import sqlite3
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
import backend
import config
from services.database import init_db
from services.runtime_settings import initialize_runtime_settings
from backend.services.models import require_loopback
from backend.api.routes import router

ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173", "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"]

@asynccontextmanager
async def lifespan(app):
    require_loopback(config.OLLAMA_URL)
    require_loopback(config.LMSTUDIO_BASE_URL)
    initialize_runtime_settings()
    config.ST_ALLOW_DOWNLOAD = False
    init_db(seed_admin=False)
    from backend.services.workflows import local_user_id
    local_user_id()
    yield

app = FastAPI(title="Colloquily local API", version="0.1.0", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type", "X-Colloquily-Token"])

@app.middleware("http")
async def local_access(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and origin not in ORIGINS:
        return JSONResponse({"detail": "Foreign browser origin denied"}, status_code=403)
    token = os.environ.get("COLLOQUILY_API_TOKEN")
    if token and request.method != "OPTIONS" and request.url.path != "/api/health":
        if not secrets.compare_digest(request.headers.get("x-colloquily-token", ""), token):
            return JSONResponse({"detail": "Desktop launch token required"}, status_code=401)
    return await call_next(request)

@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)

@app.exception_handler(sqlite3.IntegrityError)
async def conflict(request, exc):
    return JSONResponse({"detail": "A conflicting record already exists or is still referenced."}, status_code=409)

app.include_router(router)
