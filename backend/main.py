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
from backend.services.maintenance import gate, activity

ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173", "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"]

@asynccontextmanager
async def lifespan(app):
    initialize_runtime_settings()
    require_loopback(config.OLLAMA_URL)
    require_loopback(config.LMSTUDIO_BASE_URL)
    from backend.services.preferences import load_preferences
    load_preferences()
    init_db(seed_admin=False)
    from contextlib import closing
    from services.database import _connect
    with closing(_connect()) as database:
        database.execute("UPDATE subject_processing_jobs SET status='failed', error_text='PROCESSING_INTERRUPTED' WHERE status IN ('queued','running')")
        database.commit()
    from backend.services.workflows import local_user_id
    local_user_id()
    yield

app = FastAPI(title="Colloquily local API", version="0.1.3", lifespan=lifespan)
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
    if gate.update_pending and request.method not in {'GET', 'OPTIONS'} and request.url.path != '/api/system/update/cancel':
        return JSONResponse({'error': {'code': 'UPDATE_IN_PROGRESS', 'message': 'An update is being installed.'}}, status_code=409)
    exclusive = request.method == 'DELETE' or (request.method == 'POST' and request.url.path in {'/api/backups', '/api/backups/restore', '/api/system/update/begin'})
    if not gate.enter(exclusive):
        return JSONResponse({'error': {'code': 'WORKSPACE_BUSY', 'message': 'Finish running work before this operation.'}}, status_code=409)
    try:
        if exclusive:
            state = activity()
            replacing_workspace = request.url.path in {'/api/backups', '/api/backups/restore', '/api/system/update/begin'}
            if state['background_jobs'] or (replacing_workspace and state['practice_sessions']):
                return JSONResponse({'error': {'code': 'WORKSPACE_BUSY', 'message': 'Finish running jobs and practice before backup or restore.'}}, status_code=409)
        return await call_next(request)
    finally:
        gate.leave(exclusive)

@app.exception_handler(ValueError)
async def invalid(request, exc):
    message = str(exc)
    code = message if message.isupper() and " " not in message else "VALIDATION_ERROR"
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=400)

@app.exception_handler(sqlite3.IntegrityError)
async def conflict(request, exc):
    return JSONResponse({"error": {"code": "RESOURCE_CONFLICT", "message": "A conflicting record already exists or is still referenced."}}, status_code=409)

app.include_router(router)
