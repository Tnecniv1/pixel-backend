from fastapi import FastAPI, Request
from .routers import parcours, suivi
from .routers import sessions  
from .routers import progression 
from .routers import exercices
from .routers import users  # importer
from app.routers import observations
from app.routers import pixel
from dotenv import load_dotenv
load_dotenv()
from app.routers import classement
from app.routers import stats 

from fastapi.responses import FileResponse
import os

app = FastAPI(title="Pixel API", version="0.1.0")

APP_DEBUG_VERSION = "debug-headers-v1"

@app.get("/_version")
def _version():
    # Permet de vérifier que le nouveau code est bien en ligne
    return {"ok": True, "version": APP_DEBUG_VERSION}

@app.get("/_echo")
def _echo(request: Request):
    # Renvoie les headers reçus (pour voir s'il y a bien Authorization)
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
    return FileResponse(os.path.join(os.path.dirname(__file__), "reset-password.html"))

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


