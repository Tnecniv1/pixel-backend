# app/routers/pixel.py
import os
from datetime import date, datetime
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


def _calcul_malus(jours_inactif: int) -> int:
    """Calcule le malus total selon le barème de régularité."""
    malus = 0
    for jour in range(1, jours_inactif + 1):
        if jour <= 7:
            malus += 5
        elif jour <= 14:
            malus += 8
        elif jour <= 21:
            malus += 12
        else:
            malus += 100
    return malus


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

    # ─── LECTURE score_total + CALCUL MALUS RÉGULARITÉ ───────────
    malus_info = {"malus": 0, "jours_inactif": 0}
    score_total = 0

    try:
        user_res = (
            supabase.table("users_map")
            .select("last_training_date, score_base")
            .eq("user_id", user_id)
            .single()
            .execute()
        )

        user_data = user_res.data if user_res.data else {}
        last_training = user_data.get("last_training_date")
        score_total = int(user_data.get("score_base") or 0)

        if last_training:
            if isinstance(last_training, str):
                last_training = datetime.strptime(last_training, "%Y-%m-%d").date()

            jours_inactif = (date.today() - last_training).days

            if jours_inactif > 0:
                malus = _calcul_malus(jours_inactif)
                malus_info = {"malus": malus, "jours_inactif": jours_inactif}

                score_total = max(0, score_total - malus)
                supabase.table("users_map").update({
                    "score_total": score_total,
                    "last_training_date": date.today().isoformat(),
                }).eq("user_id", user_id).execute()

    except Exception as e:
        print(f"[PIXEL STATE] users_map error: {e}")

    lit = max(0, min(score_total, CAPACITY))
    ratio = lit / CAPACITY if CAPACITY else 0.0

    return {
        "user_id": user_id,
        "score_total": score_total,
        "lit": lit,
        "ratio": round(ratio, 6),
        "regularity_malus": malus_info,
    }
