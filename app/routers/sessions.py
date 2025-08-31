from fastapi import APIRouter, Body, Header, HTTPException, Query, Request
from typing import Any, Dict, List, Optional
from datetime import date, datetime
from ..services.evolution import EvolutionService
import random
from pydantic import BaseModel
from ..deps import supabase, get_auth_uid_from_bearer, user_scoped_client, service_client
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


def _get_position_par_type(user_id: int, type_op: str):
    """Retourne le parcours courant pour un type, sinon le premier parcours du type."""
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
        p_rows = (
            supabase.table("Parcours")
            .select("*")
            .eq("id", s["Parcours_Id"])
            .limit(1)
            .execute()
            .data
        )
        if p_rows and p_rows[0].get("Type_Operation") == type_op:
            return p_rows[0]

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

@router.get("/parcours/positions_currentes")
def get_positions_currentes(entrainement_id: int = Query(..., alias="entrainement_id")):
    # 1) Récupérer l'utilisateur de l'entraînement
    entr_row = (
        supabase.from_("Entrainement")
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
    evo = EvolutionService(supabase)
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
):
    """Crée un Entrainement simple pour un type donné."""
    if user_id is None:
        if not auth_uid:
            raise HTTPException(status_code=400, detail="Fournir user_id ou auth_uid")
        user_id = resolve_or_register_user_id(supabase, auth_uid, email=email)

    pos = _get_position_par_type(user_id, type)
    if not pos or "id" not in pos:
        raise HTTPException(status_code=400, detail=f"Aucun parcours disponible pour {type}")

    parcours_id = int(pos["id"])

    payload = {
        "Users_Id": user_id,
        "Parcours_Id": parcours_id,
        "Volume": volume,
        # La DB peut avoir des colonnes Date/Time (défaut côté DB ou triggers)
    }
    res = supabase.table("Entrainement").insert(payload).execute()
    data = getattr(res, "data", []) or []
    if not data:
        raise HTTPException(status_code=500, detail="Insertion Entrainement échouée")

    entrainement = data[0]
    return {
        "entrainement_id": entrainement.get("id"),
        "parcours_id": parcours_id,
        "type": pos.get("Type_Operation", type),
    }


from ..deps import user_scoped_client  # ← ajoute cet import

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
    # 1) client Supabase "scopé utilisateur" à partir du Bearer
    sb = user_scoped_client(authorization)

    if user_id is None:
        auth_uid = auth_uid or get_auth_uid_from_bearer(authorization)
        if not auth_uid:
            raise HTTPException(status_code=400, detail="Fournir user_id ou auth_uid")
        # 2) utilise sb pour résoudre/inscrire l’utilisateur
        user_id = resolve_or_register_user_id(sb, auth_uid, email=email)

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

    # 3) si ton helper accepte un client, passe sb:
    # pos_add = _get_position_par_type(user_id, "Addition", sb)
    # pos_sub = _get_position_par_type(user_id, "Soustraction", sb)
    # pos_mul = _get_position_par_type(user_id, "Multiplication", sb)
    # Sinon, garde la version actuelle et on ajustera juste après si besoin.
    pos_add = _get_position_par_type(user_id, "Addition")
    pos_sub = _get_position_par_type(user_id, "Soustraction")
    pos_mul = _get_position_par_type(user_id, "Multiplication")

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
    # 4) insert via sb (et plus supabase)
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
            pos = _get_position_par_type(user_id, t)
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
@router.post("/observations")
def post_observations(payload: Any = Body(...)):
    """Insert des observations.
    Reçoit soit un array d'objets, soit { items: [...] }.
    Champs requis par élément :
      - Entrainement_Id, Parcours_Id, Operateur_Un, Operateur_Deux, Operation, Proposition, (optionnel) Temps_Seconds, (optionnel) Correction
    """
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

    # ---------- insertion (inchangée) ----------
    print("[DEBUG] rows to insert:", rows)
    res = supabase.table("Observations").insert(rows).execute()
    data = getattr(res, "data", []) or []
    err = getattr(res, "error", None)
    if err:
        raise HTTPException(500, detail=f"Insert error: {err}")
    if not data:
        raise HTTPException(500, detail="Insertion Observations échouée")

    # ---------- ÉVALUATION D'ÉVOLUTION (ajout) ----------
    # Helper local pour normaliser l'opération côté service
    def _norm_op(db_val: str) -> Optional[str]:
        v = (db_val or "").strip().lower()
        if v in ("addition", "soustraction", "multiplication"):
            return v
        return None

    # 1) Entrainements concernés par CE batch
    entr_ids = list({r.get("Entrainement_Id") for r in data if r.get("Entrainement_Id") is not None})

    evolutions: List[Dict[str, Any]] = []
    positions_by_user: Dict[int, Dict[str, Any]] = {}
    evolution_error: Optional[str] = None   # ← utile pour débug si 500

    try:
        if entr_ids:
            # 2) Map Entrainement -> Users_Id  ✅ UTILISER from_() (lecture)
            def _query(table: str, columns: str = "*"):
                b = supabase.from_(table)
                # certains SDK n'ont pas .select()
                sel = getattr(b, "select", None)
                if callable(sel):
                    return sel(columns)
                # fallback: essayer via table()
                b2 = supabase.table(table)
                sel2 = getattr(b2, "select", None)
                if callable(sel2):
                    return sel2(columns)
                # dernier recours: renvoyer le builder tel quel
                return b

            entr_rows = (
                _query("Entrainement", "id, Users_Id")
                .in_("id", entr_ids)
                .execute()
                .data
                or []
            )
            
            entr_to_user = {int(r["id"]): int(r["Users_Id"]) for r in entr_rows if r.get("Users_Id") is not None}

            # 3) Construire les paires (user, operation) touchées dans CE batch
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

            # 4) Évaluer & enregistrer si besoin
            evo = EvolutionService(supabase)
            for uid, ops in per_user_ops.items():
                for op in ops:
                    maybe = evo.evaluate_and_record_if_needed(uid, op)
                    if maybe:
                        evolutions.append(maybe)
                # 5) Positions courantes pour ce user
                positions_by_user[uid] = evo.positions_for_user(uid)

    except Exception as e:
        # On capture l'erreur d'évolution dans la réponse (facilite le débug Postman)
        evolution_error = str(e)

    # ---------- réponse enrichie ----------
    return {
        "inserted": len(data),
        "ids": [r.get("id") for r in data],
        "evolutions": evolutions,           # liste (peut être vide si critère non atteint)
        "positions": positions_by_user,     # { user_id: { addition:{...}, soustraction:{...}, multiplication:{...} }
        "evolution_error": evolution_error  # null si RAS; string si une exception a été capturée
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
    # --- read and normalize input
    eid = body.get("Entrainement_Id") or body.get("entrainement_id")
    if not isinstance(eid, int):
        raise HTTPException(status_code=422, detail="Entrainement_Id must be an integer")

    # --- (optional) apply the user's JWT so RLS can authorize the insert/select
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            supabase.postgrest.auth(token)
        except Exception:
            # don't crash if auth() fails; RLS will still decide
            pass

    try:
        # Ensure the training exists and is visible under RLS (belongs to this user)
        ent = (
            supabase.table("Entrainement")
            .select("id, Users_Id")
            .eq("id", eid)
            .limit(1)
            .execute()
        )
        ent_row = (getattr(ent, "data", []) or [None])[0]
        if not ent_row:
            raise HTTPException(status_code=404, detail="Entrainement introuvable ou non autorisé")

        # Count existing correction attempts for this training
        # (use count="exact" if available; otherwise fallback to len(data))
        count_res = supabase.table("Corrections").select("id", count="exact").eq("Entrainement_Id", eid).execute()
        attempt = getattr(count_res, "count", None)
        if attempt is None:
            # fallback if library doesn't expose .count
            attempt = len(getattr(count_res, "data", []) or [])
        attempt += 1  # next attempt number

        # Insert the correction record
        ins = (
            supabase.table("Corrections")
            .insert({"Entrainement_Id": eid, "Tentative": attempt})
            .execute()
        )
        data = getattr(ins, "data", []) or []
        if not data:
            raise HTTPException(status_code=500, detail="Insertion Corrections échouée")

        return {"attempt": attempt, "id": data[0].get("id")}
    finally:
        # clean PostgREST context if we set a bearer
        if token:
            try:
                supabase.postgrest.auth(None)
            except Exception:
                pass

@router.get("/review/last")
def review_last_faux():
    """Retourne les observations FAUX du dernier Entrainement (non filtré par user ici)."""
    last = (
        supabase.table("Entrainement").select("id").order("id", desc=True).limit(1).execute()
    )
    ldata = getattr(last, "data", []) or []
    if not ldata:
        return {"entrainement_id": None, "count": 0, "items": []}
    eid = ldata[0]["id"]

    res = (
        supabase.table("Observations")
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
def verify_mark(body: Dict[str, Any] = Body(...)):
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

        # ignore les entrées mal formées
        if not isinstance(obs_id, int):
            continue
        if rep is None:
            missing_ids.append(obs_id)
            continue

        # Charge l'observation
        q = (
            supabase.table("Observations")
            .select("id, Entrainement_Id, Operation, Operateur_Un, Operateur_Deux, Solution")
            .eq("id", obs_id)
            .limit(1)
            .execute()
        )
        row = (getattr(q, "data", []) or [None])[0]
        if not row:
            missing_ids.append(obs_id)
            continue

        # Vérifie l'appartenance à l'entraînement
        try:
            row_eid = int(row.get("Entrainement_Id"))
        except Exception:
            row_eid = None
        if row_eid != int(eid):
            missing_ids.append(obs_id)
            continue

        # Nom d'opération : on supporte Operation (préféré) puis Type (legacy)
        op_name = row.get("Operation") or row.get("Type")
        a = row.get("Operateur_Un")
        b = row.get("Operateur_Deux")

        # Calcule attendu à la volée ; fallback sur Solution si présente
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
def review_mark_training(body: dict = Body(...)):
    """
    Body attendu :
    {
      "Entrainement_Id": <int>   // ou "entrainement_id"
    }
    -> Marque Entrainement.Correction = 'OUI'
    """
    eid = body.get("Entrainement_Id") or body.get("entrainement_id")
    if not isinstance(eid, int):
        raise HTTPException(status_code=422, detail="Champ 'Entrainement_Id' requis (int)")

    # Met à jour l'entraînement
    upd = (
        supabase.table("Entrainement")
        .update({"Correction": "OUI"})
        .eq("id", eid)
        .execute()
    )
    data = getattr(upd, "data", []) or []
    if not data:
        # soit l'id n'existe pas, soit RLS a bloqué l'update
        raise HTTPException(status_code=404, detail="Entrainement introuvable ou non autorisé")

    return {"updated": len(data), "entrainement_id": eid, "correction": "OUI"}


@router.get("/review/items")
def get_review_items(entrainement_id: Optional[int] = Query(None)) -> Dict[str, Any]:
    """
    Renvoie les Observations FAUX pour un Entrainement donné.
    - Query: ?entrainement_id=123
    - Si aucun id fourni, prend le dernier entraînement existant (fallback).
    """
    # 1) Choisir l'entrainement cible
    eid = entrainement_id
    if eid is None:
        last = (
            supabase.table("Entrainement")
            .select("id")
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        data = getattr(last, "data", []) or []
        if not data:
            return {"entrainement_id": None, "count": 0, "items": []}
        eid = int(data[0]["id"])

    # 2) Récupérer les FAUX de cet entrainement
    res = (
        supabase.table("Observations")
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
