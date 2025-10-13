# app/routers/classement.py
from fastapi import APIRouter, HTTPException, Query, Header
from typing import Optional, Literal
import os
from supabase import create_client, Client

router = APIRouter(prefix="/classement", tags=["classement"])

CAPACITY = 350 * 350

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY manquants")
sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def _me_user_id_from_bearer(authorization: Optional[str]) -> Optional[int]:
    """Résout Users_Id depuis le JWT (Auth → users_map). Ne crée rien ici."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    jwt = authorization.split(" ", 1)[1]
    try:
        u = sb.auth.get_user(jwt)
        user_obj = getattr(u, "user", None) or u
        auth_uid = user_obj.id
        m = sb.table("users_map").select("user_id").eq("auth_uid", auth_uid).maybe_single().execute()
        data = getattr(m, "data", None)
        return int(data["user_id"]) if data and "user_id" in data else None
    except Exception:
        return None

@router.get("")
def get_leaderboard(
    scope: Literal["all", "this_week"] = Query("all"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    authorization: Optional[str] = Header(None),
):
    # 1) Top N
    metric = "score_week" if scope == "this_week" else "score_global"
    try:
        resp = (
            sb.table("Classement")
            .select("Users_Id,score_global,score_week")
            .order(metric, desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        rows = getattr(resp, "data", []) or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classement fetch failed: {e}")

    items = []
    for i, r in enumerate(rows):
        score_glob = int(r.get("score_global") or 0)
        score = int(r.get("score_week") or 0) if scope == "this_week" else score_glob
        items.append({
            "rank": offset + i + 1,
            "user_id": int(r["Users_Id"]),
            "display_name": None,  # tu pourras peupler plus tard
            "score_total": score,
            "pixel_ratio": min(1.0, score_glob / CAPACITY),
        })

    # 2) "me" (position + scores)
    me = None
    me_user_id = _me_user_id_from_bearer(authorization)
    if me_user_id is not None:
        me_row = sb.table("Classement").select("score_global,score_week").eq("Users_Id", me_user_id).maybe_single().execute()
        data = getattr(me_row, "data", None)
        if data:
            my_glob = int(data.get("score_global") or 0)
            my_score = int(data.get("score_week") or 0) if scope == "this_week" else my_glob
            # rang = nb STRICTEMENT supérieurs + 1
            cnt = sb.table("Classement").select("Users_Id", count="exact", head=True).gt(metric, my_score).execute()
            greater = int(getattr(cnt, "count", 0) or 0)
            me = {
                "rank": greater + 1,
                "user_id": me_user_id,
                "display_name": None,
                "score_total": my_score,
                "pixel_ratio": min(1.0, my_glob / CAPACITY),
            }

    return {"scope": scope, "items": items, "me": me}
