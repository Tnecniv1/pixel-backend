# app/routers/parcours.py
from fastapi import APIRouter, HTTPException, Query, Header
from typing import Optional, Dict, Any, Literal, List
from ..deps import supabase, user_scoped_client  # ← ajout user_scoped_client
import logging

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/parcours", tags=["parcours"])

OpType = Literal["Addition", "Soustraction", "Multiplication"]

# -------------------------------------------------------------------
# Helpers communs (version "sb"-aware)
# -------------------------------------------------------------------
def _infer_user_id(
    sb,
    user_id: Optional[int],
    entrainement_id: Optional[int],
    parcours_id: Optional[int],
) -> Optional[int]:
    """Retrouve Users_Id à partir de l’un des 3 indices en utilisant le client lié au JWT."""
    if user_id is not None:
        return int(user_id)

    if entrainement_id is not None:
        try:
            r = (
                sb.table("Entrainement")  # ✅ singulier
                .select("Users_Id")
                .eq("id", entrainement_id)
                .limit(1)
                .execute()
            )
            row = (getattr(r, "data", []) or [None])[0]
            if row and row.get("Users_Id") is not None:
                return int(row["Users_Id"])
        except Exception:
            pass

    if parcours_id is not None:
        try:
            r = (
                sb.table("Suivi_Parcours")
                .select("Users_Id")
                .eq("Parcours_Id", parcours_id)
                .order("id", desc=True)
                .limit(1)
                .execute()
            )
            row = (getattr(r, "data", []) or [None])[0]
            if row and row.get("Users_Id") is not None:
                return int(row["Users_Id"])
        except Exception:
            pass

    return None


def _last_suivi_for_type(sb, users_id: int, typ: OpType) -> Optional[Dict[str, Any]]:
    """
    Retourne la dernière position (niveau + meta) pour un type d'opération donné.
    Cherche dans Suivi_Parcours puis résout le Parcours pour récupérer Niveau & Type.
    """
    try:
        res = (
            sb.table("Suivi_Parcours")
            .select("id,Users_Id,Parcours_Id,Date,Taux_Reussite,Type_Evolution")
            .eq("Users_Id", users_id)
            .order("id", desc=True)
            .limit(300)
            .execute()
        )
        suivis = getattr(res, "data", []) or []
    except Exception as e:
        print("[parcours] _last_suivi_for_type - err Suivi_Parcours:", e)
        return None

    for s in suivis:
        pid = s.get("Parcours_Id")
        if not pid:
            continue
        try:
            p = (
                sb.table("Parcours")
                .select("id,Niveau,Type_Operation")
                .eq("id", pid)
                .limit(1)
                .execute()
            )
            prow = (getattr(p, "data", []) or [None])[0]
        except Exception as e:
            print("[parcours] _last_suivi_for_type - err Parcours:", e)
            continue

        if not prow or prow.get("Type_Operation") != typ:
            continue

        return {
            "niveau": prow.get("Niveau"),
            "parcours_id": pid,
            "taux": s.get("Taux_Reussite"),
            "type_evolution": s.get("Type_Evolution"),
            "date": s.get("Date"),
        }

    return None


def _last_suivi_by_type(sb, users_id: int) -> Dict[str, Dict[str, Any]]:
    """
    Retourne, pour chaque type d’opération, le dernier suivi + le parcours associé
    + le critère et les 'restantes' avant prochain test critique (calculé avec Derniere_Observation_Id).
    """
    out: Dict[str, Dict[str, Any]] = {}
    seen = set()

    try:
        rs = (
            sb.table("Suivi_Parcours")
            .select("id,Users_Id,Parcours_Id,Date,Taux_Reussite,Type_Evolution,Derniere_Observation_Id")
            .eq("Users_Id", users_id)
            .order("id", desc=True)
            .limit(200)
            .execute()
        )
        suivis = getattr(rs, "data", []) or []
    except Exception as e:
        print("[parcours] _last_suivi_by_type - err Suivi_Parcours:", e)
        suivis = []

    for s in suivis:
        pid = s.get("Parcours_Id")
        if not pid:
            continue

        try:
            pr = (
                sb.table("Parcours")
                .select("id,Type_Operation,Niveau,Critere")
                .eq("id", pid)
                .limit(1)
                .execute()
            )
            prow = (getattr(pr, "data", []) or [None])[0]
        except Exception as e:
            print("[parcours] _last_suivi_by_type - err Parcours:", e)
            prow = None

        if not prow:
            continue

        typ = prow.get("Type_Operation")
        if not typ or typ in seen:
            continue

        critere = int(prow.get("Critere") or 20)
        last_obs_id = int(s.get("Derniere_Observation_Id") or 0)

        # ✅ compte les obs réalisées DEPUIS le dernier test critique
        try:
            cnt = (
                sb.table("Observations")
                .select("id", count="exact")
                .eq("Parcours_Id", pid)
                .gt("id", last_obs_id)
                .execute()
            )
            obs_since = int(getattr(cnt, "count", 0) or 0)
        except Exception:
            obs_since = 0

        restantes = max(critere - obs_since, 0)

        out[typ] = {
            "niveau": prow.get("Niveau"),
            "parcours_id": pid,
            "taux": s.get("Taux_Reussite"),
            "type_evolution": s.get("Type_Evolution"),
            "date": s.get("Date"),
            "critere": critere,
            "restantes": restantes,
        }

        seen.add(typ)
        if len(out) == 3:
            break

    return out


def _sum_user_score_via_entrainement(sb, users_id: int) -> int:
    """
    Score TOTAL = somme de Observations.Score pour *tous* les Entrainement du user.
    Ajout de logs pour comprendre ce qui est compté.
    """
    try:
        res_e = (
            sb.table("Entrainement")
            .select("id")
            .eq("Users_Id", users_id)
            .limit(50000)
            .execute()
        )
        eids: List[int] = [
            int(r["id"]) for r in (getattr(res_e, "data", []) or []) if r.get("id") is not None
        ]
        print(f"[DEBUG] Entrainement IDs for user {users_id}: {eids}")
    except Exception as e:
        print("[users.score_total] fetch Entrainement error:", e)
        eids = []

    if not eids:
        return 0

    total = 0
    BATCH = 1000
    for i in range(0, len(eids), BATCH):
        chunk = eids[i : i + BATCH]
        try:
            res_o = (
                sb.table("Observations")
                .select("id,Score,Entrainement_Id")  # log plus complet
                .in_("Entrainement_Id", chunk)
                .limit(200000)
                .execute()
            )
            rows = getattr(res_o, "data", []) or []
            obs_ids = [r.get("id") for r in rows if r.get("id") is not None]
            print(f"[DEBUG] Observations for Entrainement chunk {chunk}: {obs_ids[:20]} ... total {len(obs_ids)}")
        except Exception as e:
            print("[users.score_total] fetch Observations error:", e)
            rows = []

        for r in rows:
            sc = r.get("Score")
            if sc is None:
                continue
            try:
                total += int(float(str(sc).strip()))
            except Exception:
                pass

    print(f"[DEBUG] Final total for user {users_id}: {total}")
    return int(total)


# -------------------------------------------------------------------
# GET /parcours/position : une seule opération
# -------------------------------------------------------------------
@router.get("/position")
def get_parcours_position(
    type: OpType = Query(..., description="Addition | Soustraction | Multiplication"),
    user_id: Optional[int] = Query(None, description="Id interne utilisateur"),
    entrainement_id: Optional[int] = Query(None, description="(optionnel) via Entrainement.id"),
    parcours_id: Optional[int] = Query(None, description="(optionnel) via Suivi_Parcours.Parcours_Id"),
    authorization: Optional[str] = Header(default=None),  # ← client RLS
):
    sb = user_scoped_client(authorization)
    uid = _infer_user_id(sb, user_id, entrainement_id, parcours_id)
    if uid is None:
        raise HTTPException(
            status_code=422,
            detail="Impossible de déterminer l'utilisateur (user_id / entrainement_id / parcours_id).",
        )

    pos = _last_suivi_for_type(sb, uid, type)
    if not pos:
        return {"detail": f"Aucune position pour {type}."}
    return pos

# -------------------------------------------------------------------
# GET /parcours/positions_currentes : les 3 opérations + score global
# -------------------------------------------------------------------
@router.get("/positions_currentes")
def positions_currentes(
    user_id: Optional[int] = Query(None, description="Id interne utilisateur"),
    parcours_id: Optional[int] = Query(None, description="Parcours seed si user_id absent"),
    authorization: Optional[str] = Header(default=None),  # ← client RLS
):
    """
    Renvoie les niveaux actuels par opération (Addition/Soustraction/Multiplication),
    + score_points = somme brute de Observations.Score sur *tous* les entraînements du user,
    + score_global = moyenne des taux (si dispo).
    """
    sb = user_scoped_client(authorization)

    # 1) déterminer l'utilisateur
    uid: Optional[int] = user_id
    if uid is None and parcours_id is not None:
        try:
            sp = (
                sb.table("Suivi_Parcours")
                .select("Users_Id")
                .eq("Parcours_Id", parcours_id)
                .order("id", desc=True)
                .limit(1)
                .execute()
            )
            srow = (getattr(sp, "data", []) or [None])[0]
            if srow and srow.get("Users_Id") is not None:
                uid = int(srow["Users_Id"])
        except Exception as e:
            print("[parcours] positions_currentes - err infer user from parcours_id:", e)

    if uid is None:
        return {
            "Addition": None,
            "Soustraction": None,
            "Multiplication": None,
            "score_points": None,
            "score_global": None,
        }

    # 2) positions par type
    by_type = _last_suivi_by_type(sb, uid)

    # 3) score total (lifetime)
    try:
        score_total = _sum_user_score_via_entrainement(sb, uid)
    except Exception as e:
        print("[parcours] positions_currentes - err score total:", e)
        score_total = 0

    # 4) score_global (% moyen des taux connus)
    taux_vals = [
        v.get("taux")
        for v in by_type.values()
        if isinstance(v, dict) and isinstance(v.get("taux"), (int, float))
    ]
    score_global = round(sum(taux_vals) / len(taux_vals), 2) if taux_vals else None

    return {
        "Addition": by_type.get("Addition"),
        "Soustraction": by_type.get("Soustraction"),
        "Multiplication": by_type.get("Multiplication"),
        "score_points": score_total,
        "score_global": score_global,
    }

# -------------------------------------------------------------------
# Optionnel: endpoint dédié pour le score total
# -------------------------------------------------------------------
@router.get("/score_total")
def get_user_score_total(
    user_id: int = Query(..., description="ID interne (BIGINT) de l'utilisateur"),
    authorization: Optional[str] = Header(default=None),  # ← client RLS
):
    sb = user_scoped_client(authorization)
    total = _sum_user_score_via_entrainement(sb, user_id)
    return {"user_id": user_id, "score_points": total}

@router.get("/score_cumule")
def score_cumule(
    user_id: Optional[int] = Query(None, description="Id interne utilisateur"),
    parcours_id: Optional[int] = Query(None, description="Parcours seed pour inférer l'utilisateur"),
    window_obs: int = Query(1000, ge=100, le=5000, description="Nb max d'observations (fenêtre)"),
    bucket: int = Query(100, ge=10, le=1000, description="Taille d'un paquet d'observations"),
    authorization: Optional[str] = Header(default=None),  # ← client RLS
):
    """
    Évolution du SCORE CUMULÉ (somme de Score) toutes opérations confondues,
    par paquets de `bucket` observations, sur la fenêtre des `window_obs` dernières obs.
    Sortie: { "points": [{"x":1,"kpi":cumul1}, ...], "meta": {...} }
    """
    sb = user_scoped_client(authorization)

    # --- Résoudre l'user à partir de user_id ou parcours_id ---
    def _infer_user_from_parcours(pid: Optional[int]) -> Optional[int]:
        if pid is None:
            return None
        try:
            r = (
                sb.table("Suivi_Parcours")
                 .select("Users_Id")
                 .eq("Parcours_Id", pid)
                 .order("id", desc=True)
                 .limit(1).execute()
            )
            row = (getattr(r, "data", []) or [None])[0]
            if row and row.get("Users_Id") is not None:
                return int(row["Users_Id"])
        except Exception:
            pass
        return None

    uid = user_id or _infer_user_from_parcours(parcours_id)
    if uid is None:
        raise HTTPException(status_code=400, detail="user_id ou parcours_id requis")

    # --- IDs d'entraînements du user ---
    try:
        e = (
            sb.table("Entrainement")
             .select("id")
             .eq("Users_Id", uid)
             .order("id", desc=True)
             .limit(100000).execute()
        )
        eids = [int(r["id"]) for r in (getattr(e, "data", []) or []) if r.get("id") is not None]
        if not eids:
            return {"points": [], "meta": {"bucket": bucket, "window_obs": window_obs}}
    except Exception as ex:
        raise HTTPException(status_code=502, detail=f"Supabase error Entrainement: {ex}")

    # --- Dernières observations liées à ces entraînements (fenêtre) ---
    try:
        o = (
            sb.table("Observations")
             .select('"id","Score"')
             .in_("Entrainement_Id", eids)
             .order("id", desc=True)
             .limit(window_obs)
             .execute()
        )
        obs = getattr(o, "data", []) or []
    except Exception as ex:
        raise HTTPException(status_code=502, detail=f"Supabase error Observations: {ex}")

    if not obs:
        return {"points": [], "meta": {"bucket": bucket, "window_obs": window_obs}}

    # Ordre chronologique
    obs.sort(key=lambda r: int(r.get("id", 0)))

    # Scores (±1) -> int
    def _num(v) -> int:
        try:
            if isinstance(v, (int, float)):
                return int(v)
            if isinstance(v, str) and v.strip() != "":
                return int(float(v))
        except Exception:
            return 0
        return 0

    scores = [_num(r.get("Score")) for r in obs]

    # Paquets de `bucket` + cumul progressif
    points = []
    cumul = 0
    for i in range(0, len(scores), bucket):
        chunk = scores[i:i+bucket]
        if not chunk:
            break
        cumul += sum(chunk)
        points.append({"x": len(points)+1, "kpi": cumul})

    # Garder les 10 derniers paquets
    points = points[-10:]

    return {"points": points, "meta": {"bucket": bucket, "window_obs": window_obs}}

# --- Evolution score cumulé : 10 fenêtres de 100 obs (par défaut) -------------
@router.get("/score_timeseries")
def score_timeseries(
    user_id: int | None = Query(None, description="Id interne utilisateur (Users.id entier)"),
    parcours_id: int | None = Query(None, description="Si fourni, on infère l'utilisateur via Suivi_Parcours"),
    step: int = Query(100, ge=1, description="taille d'une fenêtre (obs/point)"),
    windows: int = Query(10, ge=1, le=50, description="nombre de points"),
    authorization: Optional[str] = Header(default=None),  # ← client RLS
):
    """
    Evolution du score CUMULÉ (toutes opérations), par tranches de `step` obs,
    sur les `windows` dernières tranches (ex: 10×100 = 1000 obs max).
    """
    sb = user_scoped_client(authorization)

    # --- 1) Résoudre l'utilisateur ---
    uid = user_id
    if uid is None and parcours_id is not None:
        try:
            r = (
                sb.table("Suivi_Parcours")
                .select("Users_Id")
                .eq("Parcours_Id", parcours_id)
                .order("id", desc=True)
                .limit(1)
                .execute()
            )
            row = (getattr(r, "data", []) or [None])[0]
            if row and row.get("Users_Id") is not None:
                uid = int(row["Users_Id"])
        except Exception as e:
            print("[score_timeseries] infer user from parcours_id error:", e)

    if uid is None:
        return {"points": [], "step": step, "windows": windows, "reason": "no_user"}

    # --- 2) Entraînements du user ---
    try:
        r_e = (
            sb.table("Entrainement")
            .select("id")
            .eq("Users_Id", uid)
            .order("id", desc=True)
            .limit(5000)
            .execute()
        )
        eids_desc = [int(x["id"]) for x in (getattr(r_e, "data", []) or []) if x.get("id") is not None]
        if not eids_desc:
            return {"points": [], "step": step, "windows": windows, "reason": "no_trainings"}
    except Exception as e:
        print("[score_timeseries] fetch Entrainement error:", e)
        return {"points": [], "step": step, "windows": windows, "reason": "err_trainings"}

    # --- 3) Observations récentes de ces entraînements ---
    target = step * windows
    try:
        r_obs = (
            sb.table("Observations")
            .select("id,Score,Entrainement_Id")
            .in_("Entrainement_Id", eids_desc)
            .order("id", desc=True)
            .limit(target)
            .execute()
        )
        obs_desc = getattr(r_obs, "data", []) or []
    except Exception as e:
        print("[score_timeseries] fetch Observations error:", e)
        return {"points": [], "step": step, "windows": windows, "reason": "err_obs"}

    if len(obs_desc) < step:
        # < 100 obs => pas assez pour 1 point
        return {"points": [], "step": step, "windows": windows, "reason": "not_enough_obs", "count": len(obs_desc)}

    # ordre chronologique
    obs = list(reversed(obs_desc))

    # --- 4) Construire les points cumulés par blocs de `step` ---
    points = []
    cumul = 0
    in_bucket = 0
    idx = 0

    for row in obs:
        s = row.get("Score")
        try:
            s = int(s) if s is not None else 0
        except Exception:
            s = 0
        cumul += s
        in_bucket += 1

        if in_bucket == step:
            idx += 1
            points.append({"x": idx, "y": cumul})
            in_bucket = 0
            if idx >= windows:
                break

    return {"points": points, "step": step, "windows": windows}
