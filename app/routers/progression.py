# app/routers/progression.py
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from typing import Literal, Optional
from collections import Counter
import datetime as dt
from typing import Literal, Optional, Dict, Any
from ..deps import supabase

router = APIRouter(prefix="/progression", tags=["progression"])

# ==========================================================
# 1) LOGIQUE D'ÉVOLUTION (inchangée) : POST /progression/analyser
# ==========================================================
@router.post("/analyser")
def analyser_progression(
    user_id: int = Query(...),
    type: str = Query(..., regex="^(Addition|Soustraction|Multiplication)$")
):
    # NOTE : cette section reprend ta logique existante.
    suivis = (supabase.table("Suivi_Parcours")
              .select("id,Parcours_Id,Derniere_Observation_Id")
              .eq("Users_Id", user_id)
              .order("id", desc=True)
              .limit(50).execute().data or [])
    suivi = None
    parcours_id = None
    critere = 20

    for s in suivis:
        prow = (supabase.table("Parcours")
                .select("id,Type_Operation,Critere")
                .eq("id", s["Parcours_Id"])
                .limit(1).execute().data or [])
        if prow and prow[0]["Type_Operation"] == type:
            suivi = s
            parcours_id = prow[0]["id"]
            critere = int(prow[0].get("Critere", 20))
            break

    if not suivi or not parcours_id:
        raise HTTPException(400, detail="Aucun suivi pour ce type (initialise d'abord)")

    last_obs_used = suivi.get("Derniere_Observation_Id") or 0

    obs = (supabase.table("Observations")
           .select("id,Etat")
           .eq("Parcours_Id", parcours_id)    # ✅ on filtre bien par Parcours_Id ici
           .gt("id", last_obs_used)
           .order("id")
           .limit(10000).execute().data or [])

    if len(obs) < critere:
        return {"status": "not_enough_data", "have": len(obs), "need": critere}

    selection = obs[-critere:]
    nb_bonnes = sum(1 for r in selection if (r.get("Etat") or "").upper() == "VRAI")
    taux = round(nb_bonnes / critere, 2)

    evolution = "stagnation"
    next_parcours_id = parcours_id

    if taux >= 0.95:
        evolution = "progression"
        nxt = (supabase.table("Parcours")
               .select("id").eq("Type_Operation", type)
               .gt("id", parcours_id).order("id").limit(1).execute().data)
        if nxt: next_parcours_id = nxt[0]["id"]
    elif taux < 0.5:
        evolution = "régression"
        prv = (supabase.table("Parcours")
               .select("id").eq("Type_Operation", type)
               .lt("id", parcours_id).order("id", desc=True).limit(1).execute().data)
        if prv: next_parcours_id = prv[0]["id"]

    last_obs_id = selection[-1]["id"]
    supabase.table("Suivi_Parcours").insert({
        "Users_Id": user_id,
        "Parcours_Id": next_parcours_id,
        "Date": datetime.now().strftime("%Y-%m-%d"),
        "Taux_Reussite": taux,
        "Type_Evolution": evolution,
        "Derniere_Observation_Id": last_obs_id
    }).execute()

    return {"status": "ok", "taux": taux, "evolution": evolution, "next_parcours_id": next_parcours_id}


# ==========================================================
# 2) ENDPOINTS READ-ONLY pour l'écran Progression
# ==========================================================

OBS_TABLE = "Observations"
# ✅ Aligné sur tes colonnes (PAS de created_at, OUI à Parcours_Id)
OBS_SELECT = '"id","Entrainement_Id","Parcours_Id","Operation","Proposition","Solution","Temps_Seconds","Marge_Erreur","Etat","Score"'

KPI = Literal["score", "taux", "erreur", "temps"]
GRAN = Literal["entrainement", "obs10", "obs50"]
OP = Literal["Addition", "Soustraction", "Multiplication", "MIXTE"]

def _num(x) -> Optional[float]:
    try:
        if isinstance(x, (int, float)): return float(x)
        if isinstance(x, str) and x.strip() != "": return float(x)
    except Exception:
        pass
    return None

def _is_ok(r: dict) -> bool:
    # Etat peut être 'VRAI' / 'FAUX' ou on compare Proposition vs Solution
    etat = (r.get("Etat") or "").upper()
    if etat in ("VRAI", "FAUX"):
        return etat == "VRAI"
    return str(r.get("Proposition")) == str(r.get("Solution"))

def _norm_op(op: str | None) -> Optional[str]:
    if not op: return None
    o = op.strip().lower()
    if o.startswith("add"): return "Addition"
    if o.startswith("sou") or o.startswith("sub"): return "Soustraction"
    if o.startswith("mul"): return "Multiplication"
    return None

def _fetch_obs(parcours_id: int | str) -> list[dict]:
    """Lit les observations d'un PARCOURS (tri par id car pas de created_at)."""
    try:
        res = (supabase.table(OBS_TABLE)
               .select(OBS_SELECT)
               .eq("Parcours_Id", parcours_id)   # ✅ filtre par parcours
               .order("id", desc=False)
               .limit(100000)
               .execute())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Supabase client error: {e}")

    if getattr(res, "error", None):
        raise HTTPException(status_code=500, detail=str(res.error))
    return getattr(res, "data", []) or []


# --- KPI time series ---------------------------------------------------------
@router.get("/kpi_timeseries")
def kpi_timeseries(
    parcours_id: int = Query(...),
    kpi: KPI = Query("taux"),
    granularite: GRAN = Query("entrainement"),
    operation: OP = Query("MIXTE"),
    limit: int = Query(100, ge=1, le=500),
):
    rows = _fetch_obs(parcours_id)

    if operation != "MIXTE":
        rows = [r for r in rows if _norm_op(r.get("Operation")) == operation]

    # Groupement
    groups: list[list[dict]] = []
    if granularite == "entrainement":
        by_eid: dict[int, list[dict]] = {}
        for r in rows:
            k = int(r.get("Entrainement_Id") or 0)
            by_eid.setdefault(k, []).append(r)
        for k_ in sorted(by_eid.keys()):
            groups.append(by_eid[k_])
    else:
        bucket = 10 if granularite == "obs10" else 50
        buf: list[dict] = []
        for r in rows:
            buf.append(r)
            if len(buf) == bucket:
                groups.append(buf); buf = []
        if buf: groups.append(buf)

    # Calcul KPI
    def calc(gr: list[dict]) -> float:
        if not gr: return 0.0
        if kpi == "score":
            # si Score présent, moyenne ; sinon ok-ko
            vals = [_num(r.get("Score")) for r in gr if _num(r.get("Score")) is not None]
            if vals: return round(sum(vals) / len(vals), 2)
            ok = sum(1 for r in gr if _is_ok(r)); ko = len(gr) - ok
            return float(ok - ko)
        if kpi == "taux":
            ok = sum(1 for r in gr if _is_ok(r))
            return round((ok/len(gr))*100, 2)
        if kpi == "erreur":
            vals = [_num(r.get("Marge_Erreur")) for r in gr]; vals = [v for v in vals if v is not None]
            return round(sum(vals)/len(vals), 2) if vals else 0.0
        if kpi == "temps":
            vals = [_num(r.get("Temps_Seconds")) for r in gr]; vals = [v for v in vals if v is not None]
            return round(sum(vals)/len(vals), 2) if vals else 0.0
        return 0.0

    pts = [{
        "x": i+1,
        "label": f"# {gr[0].get('Entrainement_Id')}" if granularite == "entrainement" and gr else str(i+1),
        "kpi": calc(gr)
    } for i, gr in enumerate(groups)]
    pts = pts[-limit:]

    # delta % (moyenne 2e moitié vs 1re moitié)
    delta_pct = None
    if len(pts) >= 4:
        mid = len(pts)//2
        a = sum(p["kpi"] for p in pts[:mid]) / max(mid,1)
        b = sum(p["kpi"] for p in pts[mid:]) / max(len(pts)-mid,1)
        if a != 0: delta_pct = round(((b-a)/abs(a))*100, 1)

    return {"points": pts, "delta_pct": delta_pct,
            "meta": {"kpi": kpi, "granularite": granularite, "operation": operation}}


# --- Régularité (courbe jour par jour) --------------------------------------
def _fetch_entrainements_dates() -> dict[int, str]:
    """
    Map Entrainement_Id -> 'YYYY-MM-DD'.
    Essaie d'abord la table 'Entrainement' (singulier), puis 'Entrainements' (pluriel).
    Essaie la colonne 'Date' puis 'date'.
    Renvoie {} si aucune combinaison ne marche.
    """
    candidates = [
        ("Entrainement", '"id","Date"'),
        ("Entrainement", '"id","date"'),
        ("Entrainements", '"id","Date"'),
        ("Entrainements", '"id","date"'),
    ]

    for table_name, select_cols in candidates:
        try:
            res = (
                supabase.table(table_name)
                .select(select_cols)
                .limit(100000)
                .execute()
            )
            data = getattr(res, "data", []) or []
        except Exception:
            continue  # essaie le candidat suivant

        out: dict[int, str] = {}
        for r in data:
            rid = r.get("id")
            raw = r.get("Date") if "Date" in r else r.get("date")
            if rid is None or not raw:
                continue
            out[int(rid)] = str(raw)[:10]  # YYYY-MM-DD
        if out:
            return out

    return {}

def _safe_iso(date_like) -> Optional[str]:
    """Convertit une valeur en string YYYY-MM-DD si possible."""
    try:
        s = str(date_like)
        return s[:10] if s else None
    except Exception:
        return None



@router.get("/regularite")
def regularite(parcours_id: int = Query(...), days: int = Query(60, ge=7, le=365)):
    rows = _fetch_obs(parcours_id)
    eid2date = _fetch_entrainements_dates()

    counts = Counter()
    any_date = False
    for r in rows:
        eid = r.get("Entrainement_Id")
        d = _safe_iso(eid2date.get(int(eid))) if eid is not None else None
        if d:
            counts[d] += 1
            any_date = True

    # si aucune date trouvée, timeline synthétique
    if not any_date:
        end = dt.date.today()
        start = end - dt.timedelta(days=days - 1)
        total = len(rows)
        if total > 0:
            per_day = max(1, total // days)
            cur = start
            remaining = total
            while cur <= end and remaining > 0:
                put = min(per_day, remaining)
                counts[cur.isoformat()] += put
                remaining -= put
                cur += dt.timedelta(days=1)

    end = dt.date.today()
    start = end - dt.timedelta(days=days - 1)
    daily = []
    tmp = best = 0
    cur = start
    while cur <= end:
        k = cur.isoformat()
        c = counts.get(k, 0)
        daily.append({"date": k, "count": c})
        if c > 0:
            tmp += 1
            best = max(best, tmp)
        else:
            tmp = 0
        cur += dt.timedelta(days=1)

    curstreak = 0
    for item in reversed(daily):
        if item["count"] > 0: curstreak += 1
        else: break

    return {"daily_counts": daily, "streak_current": curstreak, "streak_best": best}


# --- Tableau des niveaux -----------------------------------------------------
@router.get("/levels_summary")
def levels_summary(parcours_id: int = Query(...), operation: str = Query("ALL")):
    rows = _fetch_obs(parcours_id)
    if operation != "ALL":
        rows = [r for r in rows if _norm_op(r.get("Operation")) == operation]

    def agg(sub: list[dict], op_label: str, niveau: Optional[int] = None) -> dict:
        if not sub:
            return {"operation": op_label, "niveau": niveau, "volume": 0, "taux": 0.0, "temps": 0.0, "erreur": 0.0}
        ok = sum(1 for r in sub if _is_ok(r))
        t = [_num(r.get("Temps_Seconds")) for r in sub]; t = [v for v in t if v is not None]
        e = [_num(r.get("Marge_Erreur")) for r in sub]; e = [v for v in e if v is not None]
        return {
            "operation": op_label,
            "niveau": niveau,
            "volume": len(sub),
            "taux": round((ok/len(sub))*100, 1),
            "temps": round(sum(t)/len(t), 2) if t else 0.0,
            "erreur": round(sum(e)/len(e), 2) if e else 0.0,
        }

    # Regroupement par opération (et, si tu veux, par Parcours_Id pour avoir une ligne par niveau)
    by_op: dict[str, list[dict]] = {"Addition": [], "Soustraction": [], "Multiplication": []}
    for r in rows:
        k = _norm_op(r.get("Operation"))
        if k: by_op[k].append(r)

    out = []
    if operation == "ALL":
        for k, sub in by_op.items():
            if sub:
                out.append(agg(sub, k, niveau=None))  # on peut remplacer par le niveau réel si tu veux, via table Parcours
    else:
        sub = by_op.get(operation, [])
        if sub:
            out.append(agg(sub, operation, niveau=None))

    return {"rows": out}




# ---------- utils top-level (pas imbriqués) ----------
def _last_suivi_by_type(users_id: int) -> Dict[str, Dict[str, Any]]:
    """
    Retourne, pour un Users_Id donné, le dernier Suivi_Parcours par Type_Operation,
    enrichi avec le Niveau depuis Parcours.
    """
    try:
        res = (
            supabase.table("Suivi_Parcours")
            .select("id,Users_Id,Parcours_Id,Date,Taux_Reussite,Type_Evolution")
            .eq("Users_Id", users_id)
            .order("id", desc=True)
            .limit(200)
            .execute()
        )
        suivis = getattr(res, "data", []) or []
    except Exception as e:
        print("[parcours] _last_suivi_by_type - err Suivi_Parcours:", e)
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    seen = set()
    for s in suivis:
        pid = s.get("Parcours_Id")
        if not pid:
            continue
        try:
            p = (
                supabase.table("Parcours")
                .select("id,Type_Operation,Niveau")
                .eq("id", pid)
                .limit(1)
                .execute()
            )
            prow = (getattr(p, "data", []) or [None])[0]
        except Exception as e:
            print("[parcours] _last_suivi_by_type - err Parcours:", e)
            continue

        if not prow:
            continue
        typ = prow.get("Type_Operation")
        if not typ or typ in seen:
            continue
        seen.add(typ)

        out[typ] = {
            "niveau": prow.get("Niveau"),
            "parcours_id": pid,
            "taux": s.get("Taux_Reussite"),
            "type_evolution": s.get("Type_Evolution"),
            "date": s.get("Date"),
        }
        if len(out) == 3:
            break
    return out


# ---------- route unique ----------
@router.get("/positions_currentes")  # (le router a déjà prefix="/parcours")
def positions_currentes(
    user_id: Optional[int] = Query(None, description="Id interne utilisateur (pas UUID auth)"),
    parcours_id: Optional[int] = Query(None, description="Parcours seed si user_id absent"),
    entrainement_id: Optional[int] = Query(None, description="Optionnel: déduire l'utilisateur via un entraînement"),
):
    """
    Renvoie les niveaux actuels par opération pour l'utilisateur.
    Priorité: user_id -> entrainement_id -> parcours_id.
    """
    uid: Optional[int] = user_id

    # 1) via entrainement_id -> Users_Id
    if uid is None and entrainement_id is not None:
        try:
            r = (
                supabase.table("Entrainement")
                .select("id,Users_Id")
                .eq("id", entrainement_id)
                .limit(1)
                .execute()
            )
            row = (getattr(r, "data", []) or [None])[0]
            if row and row.get("Users_Id") is not None:
                uid = int(row["Users_Id"])
            else:
                return {
                    "Addition": None,
                    "Soustraction": None,
                    "Multiplication": None,
                    "score_global": None,
                    "detail": "Entrainement introuvable ou sans Users_Id",
                }
        except Exception as e:
            print("[parcours] positions_currentes - err Entrainement:", e)

    # 2) via parcours_id -> Users_Id
    if uid is None and parcours_id is not None:
        try:
            sp = (
                supabase.table("Suivi_Parcours")
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
            print("[parcours] positions_currentes - err Suivi_Parcours:", e)

    # 3) si toujours rien → réponse vide
    if uid is None:
        return {
            "Addition": None,
            "Soustraction": None,
            "Multiplication": None,
            "score_global": None,
        }

    # 4) compose la réponse
    by_type = _last_suivi_by_type(uid)

    out: Dict[str, Any] = {
        "Addition": by_type.get("Addition"),
        "Soustraction": by_type.get("Soustraction"),
        "Multiplication": by_type.get("Multiplication"),
        "score_global": None,
    }

    taux_vals = [
        v.get("taux")
        for v in by_type.values()
        if isinstance(v, dict) and isinstance(v.get("taux"), (int, float))
    ]
    if taux_vals:
        out["score_global"] = round(sum(taux_vals) / len(taux_vals), 2)

    return out


@router.get("/score_cumule_50")
def score_cumule_50(
    user_id: int = Query(..., description="ID interne Users.id (BIGINT)"),
    windows: int = Query(10, ge=1, le=20, description="Nombre de fenêtres de 50 obs (10 = 500 obs cumulées)")
):
    # 1) récup ids d'entraînements du user
    try:
        r_e = supabase.table("Entrainement").select("id").eq("Users_Id", user_id).order("id").limit(50000).execute()
        eids = [int(x["id"]) for x in (getattr(r_e,"data",[]) or []) if x.get("id") is not None]
    except Exception as e:
        raise HTTPException(502, f"Supabase error Entrainement: {e}")

    if not eids:
        return {"points": [], "meta": {"windows": windows}}

    # 2) récup observations triées par id
    try:
        r_o = (
            supabase.table("Observations")
            .select("id,Score")
            .in_("Entrainement_Id", eids)
            .order("id")
            .limit(50 * windows)   # on ne garde que les N*50 dernières obs
            .execute()
        )
        rows = getattr(r_o,"data",[]) or []
    except Exception as e:
        raise HTTPException(502, f"Supabase error Observations: {e}")

    # 3) on prend la queue (N*50 dernières)
    rows = rows[-(50 * windows):]

    # 4) regrouper par blocs de 50 (du plus ancien au plus récent)
    buckets: List[List[Dict[str,Any]]] = []
    buf: List[Dict[str,Any]] = []
    for r in rows:
        buf.append(r)
        if len(buf) == 50:
            buckets.append(buf); buf = []
    if buf:
        # si pas multiple de 50, on complète le dernier bucket
        buckets.append(buf)

    # 5) calcul score cumulé (somme des scores par bucket, cumulée)
    cum = 0
    points = []
    for i, b in enumerate(buckets, start=1):
        s = 0
        for r in b:
            sc = r.get("Score")
            try:
                if sc is not None:
                    s += int(float(str(sc)))
            except Exception:
                pass
        cum += s
        points.append({"x": i, "label": f"{i*50}", "y": cum})

    return {"points": points, "meta": {"windows": windows}}