from fastapi import FastAPI
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


app = FastAPI(title="Pixel API", version="0.1.0")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/__routes")
def list_routes():
    return [getattr(r, "path", None) for r in app.router.routes]

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