# app/routers/observations.py
from fastapi import APIRouter, HTTPException, Query
from app.deps import supabase

router = APIRouter(prefix="/observations", tags=["observations"])

TABLE_NAME = "Observations"
SELECT_COLUMNS = '"Operation","Proposition","Solution","Temps_Seconds","Marge_Erreur","Entrainement_Id"'

def norm_op(op: str | None) -> str | None:
    if not op:
        return None
    o = op.strip().lower()
    if o.startswith("add"): return "Addition"
    if o.startswith("sou") or o.startswith("sub"): return "Soustraction"
    if o.startswith("mul") or o.startswith("mult"): return "Multiplication"
    return None

@router.get("/metrics")
def metrics_of_entrainement(
    entrainement_id: int = Query(..., description="Id de l'entraînement"),
):
    try:
        res = (
            supabase.table(TABLE_NAME)
            .select(SELECT_COLUMNS)
            .eq("Entrainement_Id", entrainement_id)
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Supabase client error: {e}")

    data = getattr(res, "data", None)
    error = getattr(res, "error", None)
    if error:
        raise HTTPException(status_code=500, detail=str(error))

    rows = data or []

    # bucket par opération
    buckets = { "Addition": [], "Soustraction": [], "Multiplication": [] }

    for r in rows:
        k = norm_op(r.get("Operation"))
        if not k:
            continue
        buckets[k].append(r)

    def compute(items: list[dict]) -> dict:
        total = len(items)
        if total == 0:
            return {"successRate": 0, "avgTimeSec": 0.0, "errorMargin": 0.0, "count": 0}

        ok = sum(1 for it in items if str(it.get("Proposition")) == str(it.get("Solution")))

        times = [it.get("Temps_Seconds") for it in items if isinstance(it.get("Temps_Seconds"), (int,float))]
        errs  = [it.get("Marge_Erreur") for it in items if isinstance(it.get("Marge_Erreur"), (int,float))]

        return {
            "successRate": round((ok/total)*100),
            "avgTimeSec": sum(times)/len(times) if times else 0.0,
            "errorMargin": sum(errs)/len(errs) if errs else 0.0,
            "count": total
        }

    return {
        "Addition": compute(buckets["Addition"]),
        "Soustraction": compute(buckets["Soustraction"]),
        "Multiplication": compute(buckets["Multiplication"]),
    }
