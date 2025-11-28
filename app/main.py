from fastapi import FastAPI, Request
from .routers import parcours, suivi
from .routers import sessions  
from .routers import progression 
from .routers import exercices
from .routers import users
from app.routers import observations
from app.routers import pixel
from dotenv import load_dotenv
load_dotenv()
from app.routers import classement
from app.routers import stats 
from .routers import notifications
from .routers import notification_settings  # ← NOUVEAU

from fastapi.responses import FileResponse
import os

# ← NOUVEAU : Import pour le scheduler
from contextlib import asynccontextmanager
from app.cron.scheduler import init_scheduler, shutdown_scheduler
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ← NOUVEAU : Lifespan pour démarrer/arrêter le scheduler
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Démarrage de l'application...")
    init_scheduler()  # Démarrer les cron jobs
    
    yield
    
    # Shutdown
    logger.info("🛑 Arrêt de l'application...")
    shutdown_scheduler()  # Arrêter les cron jobs


# ← MODIFIÉ : Ajouter lifespan à FastAPI
app = FastAPI(
    title="Pixel API", 
    version="0.1.0",
    lifespan=lifespan  # ← NOUVEAU
)

APP_DEBUG_VERSION = "debug-headers-v1"

@app.get("/_version")
def _version():
    return {"ok": True, "version": APP_DEBUG_VERSION}

@app.get("/_echo")
def _echo(request: Request):
    return {
        "ok": True,
        "headers": dict(request.headers),
    }

@app.middleware("http")
async def log_auth_header(request: Request, call_next):
    auth = request.headers.get("authorization")
    short = (auth[:30] + "...") if auth else ""
    print(f"[AUTH DEBUG] path={request.url.path} auth={'present' if auth else 'missing'} {short}")
    resp = await call_next(request)
    return resp

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/__routes")
def list_routes():
    return [getattr(r, "path", None) for r in app.router.routes]

@app.get("/reset-password")
def reset_password_page():
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "reset-password.html"),
        media_type="text/html"
    )

@app.get("/email-confirmed")
def email_confirmed_page():
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "email-confirmed.html"),
        media_type="text/html"
    )

@app.get("/auth-callback")
async def auth_callback():
    """Page de redirection OAuth pour l'app mobile"""
    file_path = os.path.join(os.path.dirname(__file__), "auth-callback.html")
    return FileResponse(file_path, media_type="text/html")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

app.include_router(parcours.router, prefix="")
app.include_router(suivi.router, prefix="")
app.include_router(sessions.router, prefix="") 
app.include_router(progression.router, prefix="")  
app.include_router(exercices.router, prefix="")
app.include_router(users.router)
app.include_router(observations.router)
app.include_router(pixel.router)
app.include_router(classement.router)
app.include_router(stats.router)
app.include_router(notifications.router)
app.include_router(notification_settings.router)  # ← NOUVEAU