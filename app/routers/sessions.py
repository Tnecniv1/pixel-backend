from fastapi import APIRouter, Body, Header, HTTPException, Query
from typing import Any, Dict, List, Optional
from datetime import date, datetime, timedelta
from ..services.evolution import EvolutionService
import random
import math
from collections import defaultdict
from pydantic import BaseModel
from ..deps import supabase, get_auth_uid_from_bearer, user_scoped_client  # ← ajout user_scoped_client
from ..services.user_resolver import resolve_or_register_user_id
import os
print("[boot] sessions.py loaded from:", os.path.abspath(__file__))

# -----------------------------------------------------------------------------
# Router
# -----------------------------------------------------------------------------
router = APIRouter()

# -----------------------------------------------------------------------------
# Helpers: exercise generators + parcours position
# -----------------------------------------------------------------------------

def _gen_add(a_min: int, a_max: int, b_min: int, b_max: int):
    a = random.randint(a_min, a_max)
    b = random.randint(b_min, b_max)
    return {
        "operation": f"{a} + {b}",
        "operateur_un": a,
        "operateur_deux": b,
        "solution": a + b,
        "type": "Addition",
    }


def _gen_sub(a_min: int, a_max: int, b_min: int, b_max: int):
    a = random.randint(a_min, a_max)
    b = random.randint(b_min, b_max)
    if a < b:
        a, b = b, a
    return {
        "operation": f"{a} - {b}",
        "operateur_un": a,
        "operateur_deux": b,
        "solution": a - b,
        "type": "Soustraction",
    }


def _gen_mul(a_min: int, a_max: int, b_min: int, b_max: int):
    a = random.randint(a_min, a_max)
    b = random.randint(b_min, b_max)
    return {
        "operation": f"{a} × {b}",
        "operateur_un": a,
        "operateur_deux": b,
        "solution": a * b,
        "type": "Multiplication",
    }


def _get_position_par_type(sb, user_id: int, type_op: str):
    """Retourne le parcours courant pour un type, sinon le premier parcours du type (via client user-scopé)."""
    suivis = (
        sb.table("Suivi_Parcours")
        .select("Parcours_Id,id")
        .eq("Users_Id", user_id)
        .order("id", desc=True)
        .limit(50)
        .execute()
        .data
        or []
    )
    for s in suivis:
        p_rows = (
            sb.table("Parcours")
            .select("*")
            .eq("id", s["Parcours_Id"])
            .limit(1)
            .execute()
            .data
        )
        if p_rows and p_rows[0].get("Type_Operation") == type_op:
            return p_rows[0]

    p_rows = (
        sb.table("Parcours")
        .select("*")
        .eq("Type_Operation", type_op)
        .order("Niveau")
        .limit(1)
        .execute()
        .data
    )
    if not p_rows:
        p_rows = (
            sb.table("Parcours")
            .select("*")
            .eq("Type_Operation", type_op)
            .order("id")
            .limit(1)
            .execute()
            .data
        )
    return p_rows[0] if p_rows else None


@router.get("/parcours/positions_currentes")
def get_positions_currentes(
    entrainement_id: int = Query(..., alias="entrainement_id"),
    authorization: Optional[str] = Header(default=None),  # ← pour client user-scopé
):
    # Client lié au JWT
    sb = user_scoped_client(authorization)

    # 1) Récupérer l'utilisateur de l'entraînement
    entr_row = (
        sb.from_("Entrainement")
        .select("Users_Id")
        .eq("id", entrainement_id)
        .limit(1)
        .execute()
        .data or []
    )
    if not entr_row or entr_row[0].get("Users_Id") is None:
        raise HTTPException(404, detail="Entrainement introuvable ou sans Users_Id")

    user_id = int(entr_row[0]["Users_Id"])

    # 2) Positions courantes (auto-niveau 1 si aucun suivi)
    evo = EvolutionService(sb)  # ← utiliser le client lié au JWT
    positions = evo.positions_for_user(user_id)

    return {
        "user_id": user_id,
        "entrainement_id": entrainement_id,
        "positions": positions
    }

# -----------------------------------------------------------------------------
# Entrainements
# -----------------------------------------------------------------------------
@router.post("/entrainement/start")
def start_entrainement(
    user_id: Optional[int] = Query(None),
    auth_uid: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    type: str = Query(..., pattern="^(Addition|Soustraction|Multiplication)$"),
    volume: int = Query(..., ge=1, le=200),
    authorization: Optional[str] = Header(default=None),  # ← pour client user-scopé
):
    """Crée un Entrainement simple pour un type donné."""
    sb = user_scoped_client(authorization)

    if user_id is None:
        if not auth_uid:
            raise HTTPException(status_code=400, detail="Fournir user_id ou auth_uid")
        # user_resolver reste côté service-role (mapping users_map)
        user_id = resolve_or_register_user_id(supabase, auth_uid, email=email)

    pos = _get_position_par_type(sb, user_id, type)
    if not pos or "id" not in pos:
        raise HTTPException(status_code=400, detail=f"Aucun parcours disponible pour {type}")

    parcours_id = int(pos["id"])

    payload = {
        "Users_Id": user_id,
        "Parcours_Id": parcours_id,
        "Volume": volume,
    }
    res = sb.table("Entrainement").insert(payload).execute()
    data = getattr(res, "data", []) or []
    if not data:
        raise HTTPException(status_code=500, detail="Insertion Entrainement échouée")

    entrainement = data[0]
    return {
        "entrainement_id": entrainement.get("id"),
        "parcours_id": parcours_id,
        "type": pos.get("Type_Operation", type),
    }


@router.post("/entrainement/start_mixte")
def start_entrainement_mixte(
    user_id: Optional[int] = Query(None),
    auth_uid: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    authorization: Optional[str] = Header(default=None),
    Volume_q: Optional[int] = Query(default=None, alias="Volume"),
    volume_q: Optional[int] = Query(default=None, alias="volume"),
    body: Optional[dict] = Body(default=None),
):
    """Crée un Entrainement 'mixte' (Add+Sub+Mul) pour l'utilisateur. Volume total = volume*3."""
    sb = user_scoped_client(authorization)

    if user_id is None:
        auth_uid = auth_uid or get_auth_uid_from_bearer(authorization)
        if not auth_uid:
            raise HTTPException(status_code=400, detail="Fournir user_id ou auth_uid")
        user_id = resolve_or_register_user_id(supabase, auth_uid, email=email)

    vol = None
    if isinstance(body, dict):
        if body.get("Volume") is not None:
            vol = body["Volume"]
        elif body.get("volume") is not None:
            vol = body["volume"]
    if vol is None:
        vol = Volume_q or volume_q
    if vol is None:
        raise HTTPException(status_code=422, detail=[{"loc": ["Volume"], "msg": "Field required", "type": "missing"}])
    try:
        vol = int(vol)
        if vol < 1 or vol > 200:
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=422, detail=[{"loc": ["Volume"], "msg": "Volume must be between 1 and 200", "type": "value_error"}])

    pos_add = _get_position_par_type(sb, user_id, "Addition")
    pos_sub = _get_position_par_type(sb, user_id, "Soustraction")
    pos_mul = _get_position_par_type(sb, user_id, "Multiplication")
    if not (pos_add and pos_sub and pos_mul):
        raise HTTPException(status_code=400, detail="Positions/parcours manquants pour un des types")

    parcours_porteur_id = int(pos_add["id"])  # Addition par défaut
    payload = {
        "Users_Id": user_id,
        "Parcours_Id": parcours_porteur_id,
        "Volume": vol * 3,
        "Date": date.today().isoformat(),
        "Time": datetime.now().strftime("%H:%M:%S"),
    }
    ins = sb.table("Entrainement").insert(payload).execute()
    data = getattr(ins, "data", []) or []
    if not data:
        raise HTTPException(status_code=500, detail="Insertion Entrainement échouée")
    entrainement = data[0]

    return {
        "entrainement_id": entrainement.get("id"),
        "parcours_ids": {
            "Addition": int(pos_add["id"]),
            "Soustraction": int(pos_sub["id"]),
            "Multiplication": int(pos_mul["id"]),
        },
        "total_volume": vol * 3,
        "mode": "mixte",
    }


# -----------------------------------------------------------------------------
# Génération exercices (mixte)
# -----------------------------------------------------------------------------
@router.get("/exercices/generer_mixte")
def generer_exercices_mixte(
    user_id: Optional[int] = Query(None),
    auth_uid: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    authorization: Optional[str] = Header(default=None),
    n_q: Optional[int] = Query(default=None, alias="n"),
    Volume_q: Optional[int] = Query(default=None, alias="Volume"),
    volume_q: Optional[int] = Query(default=None, alias="volume"),
    include_solution: bool = Query(False),
    seed: Optional[int] = Query(None),
):
    """Génère n exercices par type (Add/Sub/Mul) en fonction du parcours courant de l'utilisateur."""
    sb = user_scoped_client(authorization)

    try:
        if user_id is None:
            auth_uid = auth_uid or get_auth_uid_from_bearer(authorization)
            if not auth_uid:
                raise HTTPException(status_code=400, detail="Fournir user_id ou auth_uid")
            user_id = resolve_or_register_user_id(supabase, auth_uid, email=email)

        n_val = n_q if n_q is not None else (Volume_q if Volume_q is not None else volume_q)
        if n_val is None:
            raise HTTPException(status_code=422, detail=[{"loc": ["query", "n"], "msg": "Field required (n|Volume|volume)", "type": "missing"}])
        try:
            n = int(n_val)
            if n < 1 or n > 200:
                raise ValueError()
        except Exception:
            raise HTTPException(status_code=422, detail=[{"loc": ["query", "n"], "msg": "n must be between 1 and 200", "type": "value_error"}])

        if seed is not None:
            random.seed(seed)

        types = ["Addition", "Soustraction", "Multiplication"]
        positions: Dict[str, Dict[str, Any]] = {}
        for t in types:
            pos = _get_position_par_type(sb, user_id, t)
            if not pos:
                raise HTTPException(status_code=400, detail=f"Aucun niveau (Parcours) disponible pour {t}")
            positions[t] = pos

        gens = {"Addition": _gen_add, "Soustraction": _gen_sub, "Multiplication": _gen_mul}
        exercices: List[Dict[str, Any]] = []
        for t in types:
            pos = positions[t]
            try:
                a_min = int(pos.get("Operateur1_Min", 0))
                a_max = int(pos.get("Operateur1_Max", 10))
                b_min = int(pos.get("Operateur2_Min", 0))
                b_max = int(pos.get("Operateur2_Max", 10))
            except Exception as conv_err:
                print("ERREUR conversion bornes:", t, pos, repr(conv_err))
                raise HTTPException(500, detail=f"Parcours incomplet pour {t}: bornes opérateurs manquantes")

            generator = gens[t]
            for _ in range(n):
                exo = generator(a_min, a_max, b_min, b_max)
                item = {
                    "Parcours_Id": pos["id"],
                    "Operation": exo["operation"],  # affichage
                    "Operateur_Un": exo["operateur_un"],
                    "Operateur_Deux": exo["operateur_deux"],
                    "Type": exo["type"],  # catégorie logique
                }
                if include_solution:
                    item["Solution"] = exo["solution"]
                exercices.append(item)

        return {
            "mode": "mixte",
            "total_types": len(types),
            "n_par_type": n,
            "count": len(exercices),
            "exercices": exercices,
        }

    except HTTPException:
        raise
    except Exception as e:
        print("ERREUR /exercices/generer_mixte:", repr(e))
        raise HTTPException(status_code=500, detail=f"generer_mixte: {type(e).__name__}: {e}")


# -----------------------------------------------------------------------------
# Observations (nouvelle logique : DB calcule Etat/Score/Marge_Erreur/Solution)
# -----------------------------------------------------------------------------
def _calculate_scoring(sb, entrainement_id: int, user_id: int, inserted_rows: List[Dict[str, Any]]) -> None:
    """
    Porte en Python la logique du trigger calculate_new_scoring.
    1. Une requête pour les IDs d'entraînements + une requête pour tout l'historique
       (équivalent du JOIN Observations-Entrainement WHERE Users_Id = user_id)
    2. Calcul en mémoire de bonus_vitesse, bonus_marge, score_global par Parcours_Id+Operation
    3. Mise à jour en une seule requête upsert
    Le trigger calculate_new_scoring reste actif pendant la phase de validation.
    """
    if not inserted_rows:
        return

    current_ids = {r["id"] for r in inserted_rows if r.get("id") is not None}
    if not current_ids:
        return

    # --- 1) Historique : IDs des 200 entraînements les plus récents du user ---
    entr_res = (
        sb.table("Entrainement")
        .select("id")
        .eq("Users_Id", user_id)
        .order("id", desc=True)
        .limit(200)
        .execute()
    )
    all_entr_ids = [r["id"] for r in (entr_res.data or [])]
    if not all_entr_ids:
        return

    # --- 2) Toutes les observations (historique + courantes pour Etat/Marge_Erreur du trigger) ---
    obs_res = (
        sb.table("Observations")
        .select(
            "id, Entrainement_Id, Parcours_Id, Operation, Operateur_Un, Operateur_Deux, "
            "Proposition, Correction, Temps_Seconds, Etat, Score, Solution, Marge_Erreur"
        )
        .in_("Entrainement_Id", all_entr_ids)
        .order("id", desc=True)
        .limit(2000)
        .execute()
    )
    all_obs = obs_res.data or []

    # --- 3) Séparer historique (sessions passées) et observations courantes ---
    history: List[Dict[str, Any]] = []
    current_obs: List[Dict[str, Any]] = []
    for o in all_obs:
        if o.get("id") in current_ids:
            current_obs.append(o)
        else:
            history.append(o)

    # Grouper l'historique par (Parcours_Id, Operation) — déjà trié id desc
    hist_by_key: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
    for o in history:
        hist_by_key[(o.get("Parcours_Id"), o.get("Operation"))].append(o)

    # --- 4) Calcul en mémoire ---
    HIST_MIN   = 5
    HIST_LIMIT = 50
    upsert_payloads: List[Dict[str, Any]] = []

    for obs in current_obs:
        key  = (obs.get("Parcours_Id"), obs.get("Operation"))
        hist = hist_by_key[key][:HIST_LIMIT]
        etat = str(obs.get("Etat") or "").strip()
        score_base = int(obs.get("Score") or (1 if etat == "VRAI" else -1))

        if len(hist) < HIST_MIN:
            # Pas assez d'historique → bonus nuls, score_global = Score de base
            bonus_vitesse = 0.0
            bonus_marge   = 0.0
            score_global  = score_base
        else:
            temps = float(obs.get("Temps_Seconds") or 0)
            marge = float(obs.get("Marge_Erreur") or 0)

            # Stats vitesse sur toutes les obs de l'historique
            temps_list = [float(h["Temps_Seconds"]) for h in hist if h.get("Temps_Seconds") is not None]
            if temps_list:
                mean_t = sum(temps_list) / len(temps_list)
                std_t  = (sum((x - mean_t) ** 2 for x in temps_list) / len(temps_list)) ** 0.5
            else:
                mean_t, std_t = temps, 0.0

            # Stats marge sur les FAUX uniquement
            marge_list = [
                float(h["Marge_Erreur"]) for h in hist
                if h.get("Marge_Erreur") is not None and h.get("Etat") == "FAUX"
            ]
            if marge_list:
                mean_m = sum(marge_list) / len(marge_list)
                std_m  = (sum((x - mean_m) ** 2 for x in marge_list) / len(marge_list)) ** 0.5
            else:
                mean_m, std_m = marge, 0.0

            # bonus_vitesse
            if std_t == 0 or mean_t == 0:
                bonus_vitesse = 0.0 if etat == "VRAI" else -2.0
            else:
                zone_min_t = mean_t - std_t
                zone_max_t = mean_t + std_t
                if etat == "VRAI":
                    if temps < zone_min_t:
                        bonus_vitesse = 2.0
                    elif temps > zone_max_t:
                        bonus_vitesse = -1.0
                    else:
                        bonus_vitesse = 0.0
                else:
                    bonus_vitesse = -2.0 if zone_min_t <= temps <= zone_max_t else -3.0

            # bonus_marge
            if etat == "VRAI":
                bonus_marge = 0.0
            elif std_m == 0 or mean_m == 0:
                bonus_marge = -1.0
            else:
                zone_min_m = mean_m - std_m
                zone_max_m = mean_m + std_m
                if marge < zone_min_m:
                    bonus_marge = 0.0
                elif marge > zone_max_m:
                    bonus_marge = -2.0
                else:
                    bonus_marge = -1.0

            score_global = math.floor(score_base + bonus_vitesse + bonus_marge)

        upsert_payloads.append({
            "id":            obs["id"],
            "bonus_vitesse": round(bonus_vitesse, 2),
            "bonus_marge":   round(bonus_marge, 2),
            "score_global":  score_global,
        })

    # --- 5) Mise à jour en une seule requête ---
    if upsert_payloads:
        try:
            res = supabase.table("Observations").upsert(upsert_payloads, on_conflict="id").execute()
            print(f"[scoring upsert] data count: {len(res.data or [])}, error: {getattr(res, 'error', None)}")
        except Exception as e:
            print(f"[scoring upsert] exception: {e}")


def _update_classement_after_session(sb, data: List[Dict[str, Any]]) -> None:
    """
    Relit les scores depuis Supabase après insertion et met à jour Classement + users_map
    en une seule requête chacun. Remplace le trigger trg_update_classement_on_observation.
    Prérequis : la table Classement doit avoir une colonne week_start DATE.
    """
    if not data:
        return

    # 1) Récupérer entrainement_id et Users_Id
    entrainement_id = data[0].get("Entrainement_Id")
    if entrainement_id is None:
        print("[update_classement] Entrainement_Id manquant dans data")
        return

    entr_row = (
        sb.table("Entrainement")
        .select("Users_Id")
        .eq("id", entrainement_id)
        .limit(1)
        .execute()
        .data or []
    )
    if not entr_row or entr_row[0].get("Users_Id") is None:
        print(f"[update_classement] Entrainement {entrainement_id} introuvable")
        return
    user_id = int(entr_row[0]["Users_Id"])

    # 2) Relire les scores depuis Observations
    #    (le trigger Supabase a calculé score_global au moment de l'INSERT)
    obs_rows = (
        sb.table("Observations")
        .select("score_global, Score")
        .eq("Entrainement_Id", entrainement_id)
        .execute()
        .data or []
    )
    delta_classement = sum(int(r.get("score_global") or r.get("Score") or 0) for r in obs_rows)
    delta_score_base  = sum(int(r.get("Score") or 0) for r in obs_rows)

    today  = date.today()
    monday = today - timedelta(days=today.weekday())

    # 3) Upsert Classement (score_global + score_week avec reset si nouvelle semaine)
    existing_cl = (
        sb.table("Classement")
        .select("score_global, score_week, week_start")
        .eq("Users_Id", user_id)
        .maybe_single()
        .execute()
    )
    cl = getattr(existing_cl, "data", None) or {}

    prev_global    = int(cl.get("score_global") or 0)
    prev_week      = int(cl.get("score_week") or 0)
    week_start_str = cl.get("week_start")
    if week_start_str:
        stored_monday = date.fromisoformat(str(week_start_str))
        is_new_week   = stored_monday < monday
    else:
        is_new_week = True

    new_score_week   = delta_classement if is_new_week else prev_week + delta_classement
    new_score_global = prev_global + delta_classement

    sb.table("Classement").upsert(
        {
            "Users_Id":     user_id,
            "score_global": new_score_global,
            "score_week":   new_score_week,
            "week_start":   monday.isoformat(),
        },
        on_conflict="Users_Id",
    ).execute()

    # 4) Mettre à jour users_map (score_base + last_training_date)
    user_row = (
        sb.table("users_map")
        .select("score_base")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    um = getattr(user_row, "data", None) or {}
    prev_score_base = int(um.get("score_base") or 0)

    sb.table("users_map").update({
        "score_base":         prev_score_base + delta_score_base,
        "last_training_date": today.isoformat(),
    }).eq("user_id", user_id).execute()


@router.post("/observations")
def post_observations(payload: Any = Body(...), authorization: Optional[str] = Header(default=None)):
    """Insert des observations.
    Reçoit soit un array d'objets, soit { items: [...] }.
    Champs requis par élément :
      - Entrainement_Id, Parcours_Id, Operateur_Un, Operateur_Deux, Operation, Proposition, (optionnel) Temps_Seconds, (optionnel) Correction
    """
    sb = user_scoped_client(authorization)

    # ---------- parsing entrée (inchangé) ----------
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        items = payload["items"]
    elif isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = [payload]
    else:
        raise HTTPException(422, "Payload must be a list or object with 'items'")

    rows: List[Dict[str, Any]] = []
    allowed_ops = {"Addition", "Soustraction", "Multiplication"}
    for i, it in enumerate(items):
        try:
            op_cat = str(it["Operation"]).strip()
            if op_cat not in allowed_ops:
                raise ValueError(f"Operation invalide: {op_cat}")
            row = {
                "Entrainement_Id": int(it["Entrainement_Id"]),
                "Parcours_Id": int(it["Parcours_Id"]),
                "Operateur_Un": int(it["Operateur_Un"]),
                "Operateur_Deux": int(it["Operateur_Deux"]),
                "Operation": op_cat,               # catégorie logique (DB attend la majuscule)
                "Proposition": int(it["Proposition"]),
                "Correction": str(it.get("Correction", "NON")),
                "Temps_Seconds": int(it.get("Temps_Seconds", 0)),
            }
            rows.append(row)
        except Exception as e:
            raise HTTPException(422, detail=f"Observation[{i}] invalide: {e}")

    # ---------- insertion ----------
    print("[DEBUG] rows to insert:", rows)
    CHUNK_SIZE = 20
    data = []
    for i in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[i:i + CHUNK_SIZE]
        res = sb.table("Observations").insert(chunk).execute()
        err = getattr(res, "error", None)
        if err:
            raise HTTPException(500, detail=f"Insert error (chunk {i}): {err}")
        chunk_data = getattr(res, "data", []) or []
        if not chunk_data:
            raise HTTPException(500, detail=f"Insertion Observations échouée (chunk {i})")
        data.extend(chunk_data)

    # ---------- CALCUL DU SCORING ----------
    try:
        _eid = data[0].get("Entrainement_Id") if data else None
        if _eid is not None:
            _entr = (
                sb.table("Entrainement")
                .select("Users_Id")
                .eq("id", _eid)
                .limit(1)
                .execute()
                .data or []
            )
            _uid = int(_entr[0]["Users_Id"]) if _entr and _entr[0].get("Users_Id") is not None else None
            if _uid is not None:
                _calculate_scoring(sb, int(_eid), _uid, data)
    except Exception as e:
        print(f"[post_observations] erreur calculate_scoring: {e}")

    # ---------- MISE À JOUR CLASSEMENT & users_map ----------
    try:
        _update_classement_after_session(sb, data)
    except Exception as e:
        print(f"[post_observations] erreur update_classement: {e}")

    # ---------- ÉVALUATION D'ÉVOLUTION ----------
    def _norm_op(db_val: str) -> Optional[str]:
        v = (db_val or "").strip().lower()
        if v in ("addition", "soustraction", "multiplication"):
            return v
        return None

    # 1) Entrainements concernés par CE batch
    entr_ids = list({r.get("Entrainement_Id") for r in data if r.get("Entrainement_Id") is not None})

    evolutions: List[Dict[str, Any]] = []
    positions_by_user: Dict[int, Dict[str, Any]] = {}
    evolution_error: Optional[str] = None

    try:
        if entr_ids:
            # Petit helper local qui utilise le client user-scopé
            def _query(table: str, columns: str = "*"):
                b = sb.from_(table)
                sel = getattr(b, "select", None)
                if callable(sel):
                    return sel(columns)
                b2 = sb.table(table)
                sel2 = getattr(b2, "select", None)
                if callable(sel2):
                    return sel2(columns)
                return b

            entr_rows = (
                _query("Entrainement", "id, Users_Id")
                .in_("id", entr_ids)
                .execute()
                .data
                or []
            )
            entr_to_user = {int(r["id"]): int(r["Users_Id"]) for r in entr_rows if r.get("Users_Id") is not None}

            per_user_ops: Dict[int, set] = {}
            for r in data:
                eid = r.get("Entrainement_Id")
                uid = entr_to_user.get(int(eid)) if eid is not None else None
                if uid is None:
                    continue
                op_norm = _norm_op(r.get("Operation", ""))
                if op_norm is None:
                    continue
                per_user_ops.setdefault(uid, set()).add(op_norm)

            evo = EvolutionService(sb)
            for uid, ops in per_user_ops.items():
                for op in ops:
                    maybe = evo.evaluate_and_record_if_needed(uid, op)
                    if maybe:
                        evolutions.append(maybe)
                positions_by_user[uid] = evo.positions_for_user(uid)

    except Exception as e:
        evolution_error = str(e)

    return {
        "inserted": len(data),
        "ids": [r.get("id") for r in data],
        "evolutions": evolutions,
        "positions": positions_by_user,
        "evolution_error": evolution_error
    }


# -----------------------------------------------------------------------------
# Review / Correction globale (niveau Entrainement)
# -----------------------------------------------------------------------------
class CorrectionTry(BaseModel):
    id: int        # id de l'observation FAUX
    reponse: float # réponse saisie en correction


class VerifyBody(BaseModel):
    Entrainement_Id: int
    tries: List[CorrectionTry]


@router.post("/corrections/record")
def record_correction(
    body: Dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(default=None),
):
    """
    Body: { "Entrainement_Id": <int> }  (or "entrainement_id")
    Inserts a row into Corrections with the next attempt number and returns it.
    """
    sb = user_scoped_client(authorization)

    # --- read and normalize input
    eid = body.get("Entrainement_Id") or body.get("entrainement_id")
    if not isinstance(eid, int):
        raise HTTPException(status_code=422, detail="Entrainement_Id must be an integer")

    # Ensure the training exists and is visible under RLS (belongs to this user)
    ent = (
        sb.table("Entrainement")
        .select("id, Users_Id")
        .eq("id", eid)
        .limit(1)
        .execute()
    )
    ent_row = (getattr(ent, "data", []) or [None])[0]
    if not ent_row:
        raise HTTPException(status_code=404, detail="Entrainement introuvable ou non autorisé")

    # Count existing correction attempts for this training
    count_res = sb.table("Corrections").select("id", count="exact").eq("Entrainement_Id", eid).execute()
    attempt = getattr(count_res, "count", None)
    if attempt is None:
        attempt = len(getattr(count_res, "data", []) or [])
    attempt += 1  # next attempt number

    # Insert the correction record
    ins = (
        sb.table("Corrections")
        .insert({"Entrainement_Id": eid, "Tentative": attempt})
        .execute()
    )
    data = getattr(ins, "data", []) or []
    if not data:
        raise HTTPException(status_code=500, detail="Insertion Corrections échouée")

    return {"attempt": attempt, "id": data[0].get("id")}


@router.get("/review/last")
def review_last_faux(authorization: Optional[str] = Header(default=None)):
    """Retourne les observations FAUX du dernier Entrainement (filtré par RLS du user)."""
    sb = user_scoped_client(authorization)

    last = (
        sb.table("Entrainement").select("id").order("id", desc=True).limit(1).execute()
    )
    ldata = getattr(last, "data", []) or []
    if not ldata:
        return {"entrainement_id": None, "count": 0, "items": []}
    eid = ldata[0]["id"]

    res = (
        sb.table("Observations")
        .select("id,Parcours_Id,Operation,Operateur_Un,Operateur_Deux,Solution")
        .eq("Entrainement_Id", eid)
        .eq("Etat", "FAUX")
        .order("id", desc=True)
        .execute()
    )
    items = getattr(res, "data", []) or []
    return {"entrainement_id": eid, "count": len(items), "items": items}


def _expected_from_row(op_name: Optional[str], a: Optional[int], b: Optional[int]) -> Optional[int]:
    if op_name is None or a is None or b is None:
        return None
    if op_name == "Addition":
        return a + b
    if op_name == "Soustraction":
        return a - b
    if op_name == "Multiplication":
        return a * b
    return None


@router.post("/review/verify_mark")
def verify_mark(body: Dict[str, Any] = Body(...), authorization: Optional[str] = Header(default=None)):
    """
    Body accepté (tolérant sur les noms) :
    {
      "Entrainement_Id" | "entrainement_id": <int>,
      "tries": [
        { "id" | "Observation_Id": <obsId>, "reponse" | "Reponse": <int> },
        ...
      ]
    }
    """
    sb = user_scoped_client(authorization)

    eid = body.get("Entrainement_Id") or body.get("entrainement_id")
    tries = body.get("tries") or []
    if not isinstance(eid, int) or not isinstance(tries, list):
        raise HTTPException(
            status_code=422,
            detail="Fields 'Entrainement_Id' (int) and 'tries' (array) are required"
        )

    incorrect_ids: List[int] = []
    missing_ids: List[int] = []

    for t in tries:
        obs_id = t.get("id") or t.get("Observation_Id")
        rep = t.get("reponse") if "reponse" in t else t.get("Reponse")

        if not isinstance(obs_id, int):
            continue
        if rep is None:
            missing_ids.append(obs_id)
            continue

        q = (
            sb.table("Observations")
            .select("id, Entrainement_Id, Operation, Operateur_Un, Operateur_Deux, Solution")
            .eq("id", obs_id)
            .limit(1)
            .execute()
        )
        row = (getattr(q, "data", []) or [None])[0]
        if not row:
            missing_ids.append(obs_id)
            continue

        try:
            row_eid = int(row.get("Entrainement_Id"))
        except Exception:
            row_eid = None
        if row_eid != int(eid):
            missing_ids.append(obs_id)
            continue

        op_name = row.get("Operation") or row.get("Type")
        a = row.get("Operateur_Un")
        b = row.get("Operateur_Deux")

        expected = _expected_from_row(op_name, a, b)
        if expected is None and row.get("Solution") is not None:
            try:
                expected = int(row.get("Solution"))
            except Exception:
                expected = None

        print(f"[verify_mark] obs={obs_id} op={op_name} a={a} b={b} expected={expected} got={rep}")

        try:
            rep_num = int(rep)
        except Exception:
            incorrect_ids.append(obs_id)
            continue

        if expected is None or rep_num != expected:
            incorrect_ids.append(obs_id)

    status = "ok" if not incorrect_ids and not missing_ids else "not_ok"
    return {
        "status": status,
        "updated": 0,
        "missing": len(missing_ids),
        "incorrect": len(incorrect_ids),
        "missing_ids": missing_ids,
        "incorrect_sample": [{"id": i} for i in incorrect_ids][:5],
    }


@router.post("/review/mark_training")
def review_mark_training(body: dict = Body(...), authorization: Optional[str] = Header(default=None)):
    """
    Body attendu :
    {
      "Entrainement_Id": <int>   // ou "entrainement_id"
    }
    -> Marque Entrainement.Correction = 'OUI'
    """
    sb = user_scoped_client(authorization)

    eid = body.get("Entrainement_Id") or body.get("entrainement_id")
    if not isinstance(eid, int):
        raise HTTPException(status_code=422, detail="Champ 'Entrainement_Id' requis (int)")

    upd = (
        sb.table("Entrainement")
        .update({"Correction": "OUI"})
        .eq("id", eid)
        .execute()
    )
    data = getattr(upd, "data", []) or []
    if not data:
        raise HTTPException(status_code=404, detail="Entrainement introuvable ou non autorisé")

    return {"updated": len(data), "entrainement_id": eid, "correction": "OUI"}


@router.get("/review/items")
def get_review_items(entrainement_id: Optional[int] = Query(None), authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """
    Renvoie les Observations FAUX pour un Entrainement donné.
    - Query: ?entrainement_id=123
    - Si aucun id fourni, prend le dernier entraînement existant (fallback).
    """
    sb = user_scoped_client(authorization)

    eid = entrainement_id
    if eid is None:
        last = (
            sb.table("Entrainement")
            .select("id")
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        data = getattr(last, "data", []) or []
        if not data:
            return {"entrainement_id": None, "count": 0, "items": []}
        eid = int(data[0]["id"])

    res = (
        sb.table("Observations")
        .select("id, Parcours_Id, Operation, Operateur_Un, Operateur_Deux, Solution")
        .eq("Entrainement_Id", eid)
        .eq("Etat", "FAUX")
        .order("id", desc=True)
        .execute()
    )
    items: List[Dict[str, Any]] = getattr(res, "data", []) or []

    return {"entrainement_id": eid, "count": len(items), "items": items}


# -----------------------------------------------------------------------------
# (Optionnel) Compat : anciens endpoints de correction -> 410 Gone
# -----------------------------------------------------------------------------
@router.post("/observations/corrections")
def _deprecated_mark_corrections():
    raise HTTPException(status_code=410, detail="Endpoint obsolète : utilisez /review/last et /review/verify_mark.")


@router.post("/observations/corrections_by_ids")
def _deprecated_mark_by_ids():
    raise HTTPException(status_code=410, detail="Endpoint obsolète : utilisez /review/last et /review/verify_mark.")
