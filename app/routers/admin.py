# app/routers/admin.py
"""
Endpoints analytics pour le dashboard admin.
Protection : chaque endpoint vérifie is_admin via users_map.
"""

import logging
import os
from datetime import date, datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Header, HTTPException, Query
from jose import jwt as jose_jwt
from pydantic import BaseModel

from app.deps import get_auth_uid_from_bearer, service_client

ADMIN_PASSWORD = os.getenv("ADMIN_DASHBOARD_PASSWORD", "pixel_admin_2024")
JWT_SECRET = os.getenv("JWT_SECRET", os.getenv("SUPABASE_SERVICE_ROLE_KEY", "fallback-secret"))
JWT_ALGORITHM = "HS256"

# ---------------------------------------------------------------------------
# Router login (prefix /admin)
# ---------------------------------------------------------------------------

login_router = APIRouter(prefix="/admin", tags=["admin-auth"])


class AdminLoginBody(BaseModel):
    password: str


@login_router.post("/login")
def admin_login(body: AdminLoginBody):
    if body.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")
    payload = {
        "is_admin": True,
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    token = jose_jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"access_token": token}


# ---------------------------------------------------------------------------
# Router analytics (prefix /admin/analytics)
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])

# ---------------------------------------------------------------------------
# Helper : vérifier que l'appelant est admin
# ---------------------------------------------------------------------------

def _require_admin(authorization: Optional[str]) -> None:
    if not authorization:
        raise HTTPException(status_code=401, detail="Token manquant ou invalide")

    # 1) Essayer le JWT dashboard (is_admin custom token)
    token = authorization.split(" ", 1)[1] if " " in authorization else authorization
    try:
        payload = jose_jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("is_admin"):
            return  # OK — admin dashboard token
    except Exception:
        pass

    # 2) Fallback : JWT Supabase + vérification users_map
    auth_uid = get_auth_uid_from_bearer(authorization)
    if not auth_uid:
        raise HTTPException(status_code=401, detail="Token manquant ou invalide")
    sb = service_client()
    row = (
        sb.table("users_map")
        .select("is_admin")
        .eq("auth_uid", auth_uid)
        .maybe_single()
        .execute()
    )
    data = getattr(row, "data", None)
    if not data or not data.get("is_admin"):
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")


def _period_to_days(period: str) -> int:
    return {"7d": 7, "30d": 30, "90d": 90}.get(period, 30)


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT 1 — Vue d'ensemble (KPIs globaux)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/overview")
def analytics_overview(
    period: str = Query("30d", regex="^(7d|30d|90d)$"),
    authorization: Optional[str] = Header(default=None),
):
    _require_admin(authorization)
    sb = service_client()
    days = _period_to_days(period)
    since = (date.today() - timedelta(days=days)).isoformat()

    try:
        # Total users
        total_users_res = sb.table("users_map").select("user_id", count="exact").limit(0).execute()
        total_users = total_users_res.count or 0

        # Compter TOUTES les opérations depuis le début
        total_ops_res = sb.table("Observations").select("id", count="exact").limit(0).execute()
        total_operations = total_ops_res.count if total_ops_res else 0
        logger.info(f"[OVERVIEW DEBUG] Total operations counted: {total_operations}")

        # Entrainements sur la période (pour active_users)
        ent_res = (
            sb.table("Entrainement")
            .select("id")
            .gte("Date", since)
            .limit(100000)
            .execute()
        )

        # Utilisateurs actifs (au moins 1 entrainement sur la période)
        active_ids = set()
        for e in (getattr(ent_res, "data", []) or []):
            # On a besoin de Users_Id, refaisons la requête avec le bon select
            pass

        ent_full = (
            sb.table("Entrainement")
            .select("Users_Id")
            .gte("Date", since)
            .limit(100000)
            .execute()
        )
        active_ids = {e["Users_Id"] for e in (getattr(ent_full, "data", []) or []) if e.get("Users_Id")}
        active_users = len(active_ids)

        # Premium users (abonnés via RevenueCat)
        premium_res = sb.table("users_map").select("user_id", count="exact").eq("is_subscribed", True).limit(0).execute()
        premium_users = premium_res.count or 0

        return {
            "total_users": total_users,
            "total_operations": total_operations,
            "active_users": active_users,
            "premium_users": premium_users,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[ADMIN ANALYTICS] Error in overview: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT 2 — Activité utilisateurs
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/user-activity")
def analytics_user_activity(
    period: str = Query("30d", regex="^(7d|30d|90d)$"),
    authorization: Optional[str] = Header(default=None),
):
    _require_admin(authorization)
    sb = service_client()
    days = _period_to_days(period)
    since_date = date.today() - timedelta(days=days)
    since = since_date.isoformat()
    today = date.today()

    try:
        # Tous les entrainements de la période avec Users_Id et Date
        ent_res = (
            sb.table("Entrainement")
            .select("id, Users_Id, Date")
            .gte("Date", since)
            .order("id")
            .limit(100000)
            .execute()
        )
        entrainements = getattr(ent_res, "data", []) or []

        # Tous les utilisateurs (pour display_name)
        users_res = sb.table("users_map").select("user_id, display_name").execute()
        users_map_data = {u["user_id"]: u.get("display_name", f"User {u['user_id']}") for u in (getattr(users_res, "data", []) or [])}

        # Regrouper par user
        from collections import defaultdict
        user_ent: dict = defaultdict(list)  # user_id -> list of {id, Date}
        for e in entrainements:
            uid = e.get("Users_Id")
            if uid:
                user_ent[uid].append(e)

        # Récupérer les ids d'entrainement pour compter les observations
        all_ent_ids = [e["id"] for e in entrainements]
        obs_counts: dict = defaultdict(int)  # Entrainement_Id -> count
        if all_ent_ids:
            # Compter observations par batch
            for i in range(0, len(all_ent_ids), 500):
                batch = all_ent_ids[i:i+500]
                obs_res = (
                    sb.table("Observations")
                    .select("Entrainement_Id")
                    .in_("Entrainement_Id", batch)
                    .limit(100000)
                    .execute()
                )
                for o in (getattr(obs_res, "data", []) or []):
                    obs_counts[o["Entrainement_Id"]] += 1

        users_list = []
        weeks = max(days / 7, 1)

        for uid, ents in user_ent.items():
            # Compter opérations
            total_ops = sum(obs_counts.get(e["id"], 0) for e in ents)

            # Jours uniques d'entraînement
            training_dates = set()
            last_session = None
            for e in ents:
                d = e.get("Date")
                if d:
                    training_dates.add(str(d)[:10])
                    if last_session is None or str(d) > str(last_session):
                        last_session = d

            unique_days = len(training_dates)
            days_per_week = unique_days / weeks

            # Fréquence
            if days_per_week >= 6:
                frequency = "daily"
            elif days_per_week >= 3:
                frequency = "3x_week"
            elif days_per_week >= 1:
                frequency = "weekly"
            else:
                frequency = "occasional"

            # Streak (simplifié)
            sorted_dates = sorted(training_dates, reverse=True)
            streak = 0
            check = today
            for _ in range(days):
                if check.isoformat() in training_dates:
                    streak += 1
                    check -= timedelta(days=1)
                else:
                    break

            # Churn risk : inactif > 7 jours
            churn_risk = True
            if last_session:
                try:
                    last_d = datetime.fromisoformat(str(last_session)[:10]).date()
                    churn_risk = (today - last_d).days > 7
                except Exception:
                    churn_risk = True

            users_list.append({
                "user_id": uid,
                "display_name": users_map_data.get(uid, f"User {uid}"),
                "total_operations": total_ops,
                "frequency": frequency,
                "last_session": last_session,
                "streak_days": streak,
                "churn_risk": churn_risk,
            })

        # Trier par opérations décroissantes
        users_list.sort(key=lambda u: u["total_operations"], reverse=True)

        return {"users": users_list}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur user-activity: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT 3 — Opérations par jour (graphique)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/operations-daily")
def analytics_operations_daily(
    days: int = Query(30, ge=1, le=365),
    authorization: Optional[str] = Header(default=None),
):
    _require_admin(authorization)
    sb = service_client()
    today = date.today()
    since = (today - timedelta(days=days - 1)).isoformat()

    try:
        # Récupérer entrainements avec Date
        ent_res = (
            sb.table("Entrainement")
            .select("id, Date")
            .gte("Date", since)
            .order("Date")
            .limit(100000)
            .execute()
        )
        entrainements = getattr(ent_res, "data", []) or []

        # Compter observations par entrainement
        from collections import defaultdict
        ent_by_date: dict = defaultdict(list)  # date_str -> [ent_ids]
        for e in entrainements:
            d = str(e.get("Date", ""))[:10]
            if d:
                ent_by_date[d].append(e["id"])

        # Compter toutes les observations d'un coup
        all_ent_ids = [e["id"] for e in entrainements]
        obs_per_ent: dict = defaultdict(int)
        if all_ent_ids:
            for i in range(0, len(all_ent_ids), 500):
                batch = all_ent_ids[i:i+500]
                obs_res = (
                    sb.table("Observations")
                    .select("Entrainement_Id")
                    .in_("Entrainement_Id", batch)
                    .limit(100000)
                    .execute()
                )
                for o in (getattr(obs_res, "data", []) or []):
                    obs_per_ent[o["Entrainement_Id"]] += 1

        # Agréger par date
        ops_by_date: dict = defaultdict(int)
        for d, ent_ids in ent_by_date.items():
            for eid in ent_ids:
                ops_by_date[d] += obs_per_ent.get(eid, 0)

        # Générer toutes les dates (y compris celles à 0)
        data = []
        current = today - timedelta(days=days - 1)
        while current <= today:
            d_str = current.isoformat()
            data.append({
                "date": d_str,
                "total_operations": ops_by_date.get(d_str, 0),
            })
            current += timedelta(days=1)

        return {"data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur operations-daily: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT 3b — Opérations cumulatives (graphique all-time)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/operations-cumulative")
def analytics_operations_cumulative(
    authorization: Optional[str] = Header(default=None),
):
    _require_admin(authorization)
    sb = service_client()

    try:
        from collections import defaultdict

        # Récupérer TOUS les entrainements avec leur Date (sans filtre de période)
        all_entrainements = []
        offset = 0
        batch_size = 10000
        while True:
            ent_res = (
                sb.table("Entrainement")
                .select("id, Date")
                .order("Date")
                .range(offset, offset + batch_size - 1)
                .execute()
            )
            batch = getattr(ent_res, "data", []) or []
            all_entrainements.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size

        # Map entrainement_id -> date
        ent_date_map: dict = {}
        for e in all_entrainements:
            d = str(e.get("Date", ""))[:10]
            if d:
                ent_date_map[e["id"]] = d

        all_ent_ids = list(ent_date_map.keys())

        # Compter les observations par date
        ops_by_date: dict = defaultdict(int)
        if all_ent_ids:
            for i in range(0, len(all_ent_ids), 500):
                batch = all_ent_ids[i:i + 500]
                obs_res = (
                    sb.table("Observations")
                    .select("Entrainement_Id")
                    .in_("Entrainement_Id", batch)
                    .limit(100000)
                    .execute()
                )
                for o in (getattr(obs_res, "data", []) or []):
                    eid = o.get("Entrainement_Id")
                    d = ent_date_map.get(eid)
                    if d:
                        ops_by_date[d] += 1

        # Trier les dates et calculer le cumulatif
        sorted_dates = sorted(ops_by_date.keys())
        if not sorted_dates:
            return {"data": []}

        # Générer toutes les dates entre la première et aujourd'hui
        first_date = date.fromisoformat(sorted_dates[0])
        today = date.today()
        data = []
        cumulative = 0
        day_number = 1
        current = first_date
        while current <= today:
            d_str = current.isoformat()
            cumulative += ops_by_date.get(d_str, 0)
            data.append({
                "day": day_number,
                "date": d_str,
                "total_operations": cumulative,
            })
            day_number += 1
            current += timedelta(days=1)

        logger.info(f"[CUMULATIVE DEBUG] {len(data)} days, final total: {cumulative}")
        return {"data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur operations-cumulative: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT 4 — Funnel de conversion
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/conversion-funnel")
def analytics_conversion_funnel(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    authorization: Optional[str] = Header(default=None),
):
    _require_admin(authorization)
    sb = service_client()

    try:
        # Impressions & downloads : depuis analytics_manual_data
        impressions = 0
        downloads = 0
        try:
            md_q = sb.table("analytics_manual_data").select("impressions, downloads")
            if start_date:
                md_q = md_q.gte("date", start_date)
            if end_date:
                md_q = md_q.lte("date", end_date)
            md_res = md_q.execute()
            md_data = getattr(md_res, "data", []) or []
            for row in md_data:
                impressions += row.get("impressions", 0) or 0
                downloads += row.get("downloads", 0) or 0
        except Exception:
            # Table n'existe pas encore → 0
            pass

        # Compter users ayant au moins 1 entrainement
        training_res = sb.table("Entrainement").select("Users_Id").execute()

        if training_res.data:
            # Filtrer les None et compter les uniques
            user_ids = [t["Users_Id"] for t in training_res.data if t.get("Users_Id") is not None]
            users_with_training = len(set(user_ids))
        else:
            users_with_training = 0

        logger.info(f"[FUNNEL DEBUG] Training entries: {len(training_res.data) if training_res.data else 0}, Unique users: {users_with_training}")

        # Subscriptions (abonnés via RevenueCat)
        sub_res = sb.table("users_map").select("user_id", count="exact").eq("is_subscribed", True).limit(0).execute()
        subscriptions = sub_res.count or 0

        return {
            "impressions": impressions,
            "downloads": downloads,
            "users_with_training": users_with_training,
            "subscriptions": subscriptions,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[ADMIN ANALYTICS] Error in conversion-funnel: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT 5 — Saisir données manuelles (impressions/downloads)
# ═══════════════════════════════════════════════════════════════════════════

class ManualDataIn(BaseModel):
    date: str  # YYYY-MM-DD
    impressions: int = 0
    downloads: int = 0


@router.post("/manual-data")
def analytics_manual_data(
    body: ManualDataIn,
    authorization: Optional[str] = Header(default=None),
):
    _require_admin(authorization)
    sb = service_client()

    try:
        # Upsert : on tente un update, si 0 rows → insert
        existing = (
            sb.table("analytics_manual_data")
            .select("date")
            .eq("date", body.date)
            .maybe_single()
            .execute()
        )
        if getattr(existing, "data", None):
            sb.table("analytics_manual_data").update({
                "impressions": body.impressions,
                "downloads": body.downloads,
            }).eq("date", body.date).execute()
        else:
            sb.table("analytics_manual_data").insert({
                "date": body.date,
                "impressions": body.impressions,
                "downloads": body.downloads,
            }).execute()

        return {"ok": True, "date": body.date}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur manual-data: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT 6 — Taux de réussite moyen par jour
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/success-rate-daily")
def analytics_success_rate_daily(
    days: int = Query(30, ge=1, le=365),
    authorization: Optional[str] = Header(default=None),
):
    _require_admin(authorization)
    sb = service_client()
    today = date.today()
    since = (today - timedelta(days=days - 1)).isoformat()

    try:
        # Récupérer entrainements avec Date
        ent_res = (
            sb.table("Entrainement")
            .select("id, Date")
            .gte("Date", since)
            .order("Date")
            .limit(100000)
            .execute()
        )
        entrainements = getattr(ent_res, "data", []) or []

        from collections import defaultdict
        ent_date_map: dict = {}  # ent_id -> date_str
        for e in entrainements:
            d = str(e.get("Date", ""))[:10]
            if d:
                ent_date_map[e["id"]] = d

        all_ent_ids = list(ent_date_map.keys())

        # Observations avec Etat
        # Etat = "JUSTE" ou "FAUX" (la DB calcule automatiquement)
        daily_correct: dict = defaultdict(int)
        daily_total: dict = defaultdict(int)

        if all_ent_ids:
            for i in range(0, len(all_ent_ids), 500):
                batch = all_ent_ids[i:i+500]
                obs_res = (
                    sb.table("Observations")
                    .select("Entrainement_Id, Etat")
                    .in_("Entrainement_Id", batch)
                    .limit(100000)
                    .execute()
                )
                for o in (getattr(obs_res, "data", []) or []):
                    eid = o.get("Entrainement_Id")
                    d = ent_date_map.get(eid)
                    if d:
                        daily_total[d] += 1
                        if str(o.get("Etat", "")).upper() != "FAUX":
                            daily_correct[d] += 1

        # Générer toutes les dates
        data = []
        current = today - timedelta(days=days - 1)
        while current <= today:
            d_str = current.isoformat()
            total = daily_total.get(d_str, 0)
            correct = daily_correct.get(d_str, 0)
            rate = round((correct / total) * 100, 1) if total > 0 else 0.0
            data.append({
                "date": d_str,
                "success_rate": rate,
            })
            current += timedelta(days=1)

        return {"data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur success-rate-daily: {e}")
