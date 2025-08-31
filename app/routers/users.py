from fastapi import APIRouter, HTTPException, Query, Request
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
    authorization: str = Header(default=None)
    ):

    raw_ids = [x for x in ids.split(",") if x.strip()]
    if not raw_ids:
        return {"users": []}

    sb = user_scoped_client(request.headers.get("authorization"))
    q = sb.table("Users").select("id, name").in_("id", raw_ids).execute()    data = getattr(q, "data", []) or []
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