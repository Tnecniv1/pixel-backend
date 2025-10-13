from fastapi import APIRouter, HTTPException, Query
from typing import Literal, List, Dict, Any, Optional
from ..deps import supabase
import random
from ..services.user_resolver import resolve_or_register_user_id

router = APIRouter()

def _get_position_par_type(user_id: int, type_op: str) -> Optional[Dict[str, Any]]:
    """Récupère la position ACTUELLE (Parcours) pour ce user et ce type,
    sinon renvoie le premier niveau du type."""
    # Derniers suivis
    suivis = (
        supabase.table("Suivi_Parcours")
        .select("Parcours_Id,id")
        .eq("Users_Id", user_id)
        .order("id", desc=True)
        .limit(50)
        .execute()
        .data
        or []
    )
    for s in suivis:
        prow = (
            supabase.table("Parcours")
            .select("*")
            .eq("id", s["Parcours_Id"])
            .limit(1)
            .execute()
            .data
            or []
        )
        if prow and prow[0].get("Type_Operation") == type_op:
            return prow[0]

    # Fallback: premier niveau du type
    p_rows = (
        supabase.table("Parcours")
        .select("*")
        .eq("Type_Operation", type_op)
        .order("Niveau")
        .limit(1)
        .execute()
        .data
    )
    if not p_rows:
        p_rows = (
            supabase.table("Parcours")
            .select("*")
            .eq("Type_Operation", type_op)
            .order("id")
            .limit(1)
            .execute()
            .data
        )
    return p_rows[0] if p_rows else None


def _gen_add(a_min:int, a_max:int, b_min:int, b_max:int) -> dict:
    a = random.randint(a_min, a_max)
    b = random.randint(b_min, b_max)
    return {
        "operateur_un": a,
        "operateur_deux": b,
        "operation": f"{a} + {b}",
        "solution": a + b,
        "type": "Addition",
    }

def _gen_sub(a_min:int, a_max:int, b_min:int, b_max:int) -> dict:
    a = random.randint(a_min, a_max)
    b = random.randint(b_min, b_max)
    # éviter les résultats négatifs pour des niveaux débutants
    if b > a:
        a, b = b, a
    return {
        "operateur_un": a,
        "operateur_deux": b,
        "operation": f"{a} - {b}",
        "solution": a - b,
        "type": "Soustraction",
    }

def _gen_mul(a_min:int, a_max:int, b_min:int, b_max:int) -> dict:
    a = random.randint(a_min, a_max)
    b = random.randint(b_min, b_max)
    return {
        "operateur_un": a,
        "operateur_deux": b,
        "operation": f"{a} × {b}",
        "solution": a * b,
        "type": "Multiplication",
    }

@router.get("/exercices/generer")
@router.get("/exercices/generer")
def generer_exercices(
    user_id: Optional[int] = Query(None),
    auth_uid: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    type: str = Query(..., pattern="^(Addition|Soustraction|Multiplication)$"),
    n: int = Query(..., ge=1, le=200),
    include_solution: bool = Query(False),
    seed: Optional[int] = Query(None),
):
    """
    Génère n exercices adaptés au niveau courant (Parcours) pour ce type.
    Utilise Operateur1_Min/Max & Operateur2_Min/Max du Parcours.
    """
    # 1) Résoudre / créer user_id à partir de auth_uid (backend robuste)
    if user_id is None:
        if not auth_uid:
            raise HTTPException(status_code=400, detail="Fournir user_id ou auth_uid")
        user_id = resolve_or_register_user_id(supabase, auth_uid, email=email)

    # 2) Seed optionnel pour tests déterministes
    if seed is not None:
        random.seed(seed)

    # 3) Récupérer la position (parcours) du user pour ce type
    pos = _get_position_par_type(user_id, type)
    if not pos:
        raise HTTPException(status_code=400, detail=f"Aucun niveau disponible pour {type}")

    try:
        a_min = int(pos.get("Operateur1_Min", 0))
        a_max = int(pos.get("Operateur1_Max", 10))
        b_min = int(pos.get("Operateur2_Min", 0))
        b_max = int(pos.get("Operateur2_Max", 10))
    except Exception:
        raise HTTPException(status_code=500, detail="Parcours incomplet: bornes opérateurs manquantes")

    gens = {
        "Addition": _gen_add,
        "Soustraction": _gen_sub,
        "Multiplication": _gen_mul,
    }
    generator = gens[type]

    out: List[Dict[str, Any]] = []
    for _ in range(n):
        exo = generator(a_min, a_max, b_min, b_max)
        item: Dict[str, Any] = {
            "Parcours_Id": pos["id"],
            "Operation": exo["operation"],
            "Operateur_Un": exo["operateur_un"],
            "Operateur_Deux": exo["operateur_deux"],
            "Type": exo["type"],
        }
        if include_solution:
            item["Solution"] = exo["solution"]
        out.append(item)

    return {
        "parcours_id": pos["id"],
        "type": type,
        "niveau": pos.get("Niveau"),
        "count": len(out),
        "exercices": out,
    }