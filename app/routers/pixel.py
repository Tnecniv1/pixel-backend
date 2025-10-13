# app/routers/pixel.py
import os
from fastapi import APIRouter, HTTPException, Query
from supabase import create_client, Client
from app.services.user_resolver import resolve_or_register_user_id

router = APIRouter(prefix="/pixel", tags=["pixel"])

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY manquant. Charge ton .env au démarrage.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

CAPACITY = 350 * 350  # 122_500

@router.get("/state")
def get_pixel_state(auth_uid: str = Query(..., description="UUID Supabase de l'utilisateur")):
    """
    Version test: passe auth_uid en query. Ex: /pixel/state?auth_uid=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    """
    # 1) Résoudre user_id via ton resolver
    try:
        user_id = resolve_or_register_user_id(supabase, auth_uid)
    except Exception as e:
        # erreur la plus fréquente : clé anon => insert interdit par RLS
        raise HTTPException(status_code=500, detail=f"User resolver failed: {e}")

    # 2) Récupérer les scores Observations reliés à Entrainement.Users_Id = user_id
    #    IMPORTANT: utiliser la jointure PostgREST explicite avec !inner
    try:
        resp = (
            supabase.table("Observations")
            .select('Score, Entrainement!inner(Users_Id)')
            .eq('Entrainement.Users_Id', user_id)
            .execute()
        )
        rows = getattr(resp, "data", []) or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase select failed: {e}")

    # 3) Somme des scores (None -> 0)
    score_total = 0
    for r in rows:
        v = r.get("Score")
        if isinstance(v, (int, float)):
            score_total += int(v)

    lit = max(0, min(score_total, CAPACITY))
    ratio = lit / CAPACITY if CAPACITY else 0.0

    return {
        "user_id": user_id,
        "score_total": score_total,
        "lit": lit,
        "ratio": round(ratio, 6),
        "count": len(rows),  # utile pour debug rapide
    }
