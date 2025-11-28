from fastapi import APIRouter, HTTPException, Query, Request, Header
from pydantic import BaseModel, EmailStr
from ..deps import supabase, user_scoped_client
from ..services.user_resolver import resolve_or_register_user_id
from typing import List, Union
from pydantic import BaseModel

router = APIRouter(prefix="/users", tags=["users"])

class ResolveIn(BaseModel):
    auth_uid: str
    email: EmailStr | None = None
    name: str | None = None

class ResolveOut(BaseModel):
    user_id: int

@router.post("/resolve", response_model=ResolveOut)
def resolve_user(payload: ResolveIn):
    try:
        uid = resolve_or_register_user_id(supabase, payload.auth_uid, payload.email, payload.name)
        return {"user_id": uid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class ResolveIdsIn(BaseModel):
    ids: List[Union[int, str]]

@router.get("/resolve")
def resolve_display_names_get(
    ids: str = Query(""),
    authorization: str | None = Header(default=None),
):
    """
    Ex: /users/resolve?ids=1,2,8
    Retourne: {"users":[{"id":1,"name":"Alice"}, ...]}
    """
    # 1) parser les IDs
    raw_ids = [x.strip() for x in ids.split(",") if x.strip()]
    # optionnel: garder que les entiers
    try:
        id_list = [int(x) for x in raw_ids]
    except ValueError:
        raise HTTPException(status_code=422, detail="ids must be integers, comma-separated")

    if not id_list:
        return {"users": []}

    # 2) client Supabase lié au JWT
    sb = user_scoped_client(authorization)

    # 3) requête
    q = sb.table("Users").select("id, name").in_("id", id_list).execute()
    data = getattr(q, "data", []) or []

    out = [{"id": int(r["id"]), "name": r.get("name") or ""} for r in data if "id" in r]
    return {"users": out}



@router.post("/resolve")
def resolve_display_names_post(body: ResolveIdsIn):
    """
    Alternative POST avec body: {"ids":[1,2,8]}
    """
    if not body.ids:
        return {"users": []}
    q = supabase.table("Users").select("id, name").in_("id", body.ids).execute()
    data = getattr(q, "data", []) or []
    out = [{"id": int(r["id"]), "name": r.get("name") or ""} for r in data if "id" in r]
    return {"users": out}

    
@router.get("/debug/get-token")  # ← Change POST en GET
async def debug_get_token(email: str, password: str):
    """Endpoint temporaire pour récupérer un token"""
    from ..deps import service_client
    supabase = service_client()
    
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        return {
            "access_token": response.session.access_token,
            "user_id": response.user.id
        }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail=f"Erreur connexion: {str(e)}")