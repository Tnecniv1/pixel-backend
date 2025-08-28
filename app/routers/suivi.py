from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from ..deps import supabase

router = APIRouter()

def _first_parcours_id(type_op: str):
    rows = (supabase.table("Parcours")
            .select("id")
            .eq("Type_Operation", type_op)
            .order("Niveau")
            .limit(1).execute().data or [])
    if not rows:
        rows = (supabase.table("Parcours")
                .select("id")
                .eq("Type_Operation", type_op)
                .order("id")
                .limit(1).execute().data or [])
    return rows[0]["id"] if rows else None

@router.post("/suivi/init")
def init_suivi(user_id: int = Query(..., description="Users.id existant")):
    types = ["Addition", "Soustraction", "Multiplication"]
    today = datetime.now().strftime("%Y-%m-%d")

    exist = (supabase.table("Suivi_Parcours")
             .select("id,Parcours_Id")
             .eq("Users_Id", user_id)
             .order("id", desc=True)
             .limit(100).execute().data or [])

    deja = set()
    for s in exist:
        p = (supabase.table("Parcours")
             .select("id,Type_Operation")
             .eq("id", s["Parcours_Id"])
             .limit(1).execute().data or [])
        if p:
            deja.add(p[0]["Type_Operation"])

    created = []
    for t in types:
        if t in deja:
            continue
        pid = _first_parcours_id(t)
        if not pid:
            raise HTTPException(400, detail=f"Aucun Parcours pour {t}")
        supabase.table("Suivi_Parcours").insert({
            "Users_Id": user_id,
            "Parcours_Id": pid,
            "Date": today,
            "Taux_Reussite": 0,
            "Type_Evolution": "initialisation",
            "Derniere_Observation_Id": None
        }).execute()
        created.append({"type": t, "Parcours_Id": pid})

    return {"status": "ok", "created": created}
