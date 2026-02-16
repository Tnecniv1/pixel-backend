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
# ENDPOINT 3b — Opérations par jour (non cumulé)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/operations-cumulative")
def analytics_operations_daily_activity(
    days: Optional[int] = Query(None, description="Nombre de jours (ex: 90). Si absent, toute la période."),
    authorization: Optional[str] = Header(default=None),
):
    _require_admin(authorization)
    sb = service_client()

    try:
        from collections import defaultdict

        today = date.today()

        # Récupérer les entrainements (avec pagination pour dépasser la limite Supabase de 1000)
        if days is not None:
            cutoff_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        else:
            cutoff_date = None

        logger.info(f"[ACTIVITY] Today: {today}")
        logger.info(f"[ACTIVITY] Cutoff date: {cutoff_date}")

        all_entrainements = []
        page_size = 1000
        offset = 0
        while True:
            query = sb.table("Entrainement").select("id, Date")
            if cutoff_date:
                query = query.gte("Date", cutoff_date)
            query = query.order("id").range(offset, offset + page_size - 1)
            ent_res = query.execute()
            page_data = getattr(ent_res, "data", []) or []
            all_entrainements.extend(page_data)
            if len(page_data) < page_size:
                break
            offset += page_size

        logger.info(f"[ACTIVITY] Total entrainements found: {len(all_entrainements)}")

        # Map entrainement_id -> date
        ent_date_map: dict = {}
        for e in all_entrainements:
            d = str(e.get("Date", ""))[:10]
            if d:
                ent_date_map[e["id"]] = d

        all_ent_ids = list(ent_date_map.keys())

        # Compter les observations par date (avec pagination par batch)
        ops_by_date: dict = defaultdict(int)
        if all_ent_ids:
            for i in range(0, len(all_ent_ids), 500):
                batch = all_ent_ids[i:i + 500]
                obs_offset = 0
                while True:
                    obs_res = (
                        sb.table("Observations")
                        .select("Entrainement_Id")
                        .in_("Entrainement_Id", batch)
                        .order("id")
                        .range(obs_offset, obs_offset + page_size - 1)
                        .execute()
                    )
                    obs_data = getattr(obs_res, "data", []) or []
                    for o in obs_data:
                        eid = o.get("Entrainement_Id")
                        d = ent_date_map.get(eid)
                        if d:
                            ops_by_date[d] += 1
                    if len(obs_data) < page_size:
                        break
                    obs_offset += page_size

        # Déterminer la date de début
        if days is not None:
            first_date = today - timedelta(days=days - 1)
        else:
            sorted_dates = sorted(ops_by_date.keys())
            if not sorted_dates:
                return {"data": []}
            first_date = date.fromisoformat(sorted_dates[0])

        # Générer toutes les dates avec opérations par jour (non cumulé)
        data = []
        current = first_date
        while current <= today:
            d_str = current.isoformat()
            data.append({
                "date": d_str,
                "operations": ops_by_date.get(d_str, 0),
            })
            current += timedelta(days=1)

        dates = [d["date"] for d in data]
        logger.info(f"[ACTIVITY] Date range: {min(dates) if dates else 'N/A'} to {max(dates) if dates else 'N/A'}")
        logger.info(f"[ACTIVITY] Total days returned: {len(data)}, Entrainements fetched: {len(all_entrainements)}")

        return {"data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur operations-cumulative: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT 3c — Matrice de régularité des utilisateurs
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/user-regularity-matrix")
def analytics_user_regularity_matrix(
    authorization: Optional[str] = Header(default=None),
):
    _require_admin(authorization)
    sb = service_client()

    try:
        from collections import defaultdict
        import calendar

        today = date.today()
        yesterday = today - timedelta(days=1)

        # --- Bornes temporelles ---
        # Semaine actuelle (lundi = 0)
        week_start = today - timedelta(days=today.weekday())
        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = week_start - timedelta(days=1)

        # Mois actuel
        month_start = today.replace(day=1)
        prev_month_last_day = month_start - timedelta(days=1)
        prev_month_start = prev_month_last_day.replace(day=1)
        days_in_current_month = calendar.monthrange(today.year, today.month)[1]
        days_in_prev_month = calendar.monthrange(prev_month_last_day.year, prev_month_last_day.month)[1]

        # --- Récupérer TOUS les entrainements (paginé) ---
        all_entrainements = []
        page_size = 1000
        offset = 0
        while True:
            ent_res = (
                sb.table("Entrainement")
                .select("id, Users_Id, Date")
                .order("id")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            page_data = getattr(ent_res, "data", []) or []
            all_entrainements.extend(page_data)
            if len(page_data) < page_size:
                break
            offset += page_size

        if not all_entrainements:
            return {"global_regularity": 0.0, "users": []}

        # Map entrainement -> (user_id, date_str)
        ent_info: dict = {}  # ent_id -> (user_id, date_str)
        user_ent_ids: dict = defaultdict(list)  # user_id -> [ent_ids]
        for e in all_entrainements:
            uid = e.get("Users_Id")
            d = str(e.get("Date", ""))[:10]
            if uid and d:
                ent_info[e["id"]] = (uid, d)
                user_ent_ids[uid].append(e["id"])

        all_ent_ids = list(ent_info.keys())

        # --- Compter observations par entrainement (paginé) ---
        obs_per_ent: dict = defaultdict(int)
        if all_ent_ids:
            for i in range(0, len(all_ent_ids), 500):
                batch = all_ent_ids[i:i + 500]
                obs_offset = 0
                while True:
                    obs_res = (
                        sb.table("Observations")
                        .select("Entrainement_Id")
                        .in_("Entrainement_Id", batch)
                        .order("id")
                        .range(obs_offset, obs_offset + page_size - 1)
                        .execute()
                    )
                    obs_data = getattr(obs_res, "data", []) or []
                    for o in obs_data:
                        obs_per_ent[o["Entrainement_Id"]] += 1
                    if len(obs_data) < page_size:
                        break
                    obs_offset += page_size

        # --- Construire les données par utilisateur ---
        # user_id -> {dates: set, ops_by_date: {date_str: int}}
        user_data: dict = defaultdict(lambda: {"dates": set(), "ops_by_date": defaultdict(int)})
        for ent_id, (uid, d_str) in ent_info.items():
            user_data[uid]["dates"].add(d_str)
            user_data[uid]["ops_by_date"][d_str] += obs_per_ent.get(ent_id, 0)

        # --- Display names ---
        users_res = sb.table("users_map").select("user_id, display_name").execute()
        display_names = {
            u["user_id"]: u.get("display_name") or f"User {u['user_id']}"
            for u in (getattr(users_res, "data", []) or [])
        }

        # --- Helper : compter ops et jours dans une plage ---
        def _ops_and_days_in_range(ops_by_date, dates_set, start, end):
            ops = 0
            active_days = 0
            current = start
            while current <= end:
                d_str = current.isoformat()
                if d_str in dates_set:
                    active_days += 1
                ops += ops_by_date.get(d_str, 0)
                current += timedelta(days=1)
            return ops, active_days

        def _trend(current_val, previous_val):
            if current_val > previous_val:
                return "up"
            elif current_val < previous_val:
                return "down"
            return "neutral"

        # --- Calculer par utilisateur ---
        users_list = []
        all_indices = []

        for uid, ud in user_data.items():
            dates_set = ud["dates"]
            ops_by_date = ud["ops_by_date"]
            total_ops = sum(ops_by_date.values())

            # JOUR
            ops_today = ops_by_date.get(today.isoformat(), 0)
            ops_yesterday = ops_by_date.get(yesterday.isoformat(), 0)
            day_index = 1.0 if today.isoformat() in dates_set else 0.0

            # SEMAINE
            ops_week, days_week = _ops_and_days_in_range(ops_by_date, dates_set, week_start, today)
            ops_prev_week, _ = _ops_and_days_in_range(ops_by_date, dates_set, prev_week_start, prev_week_end)
            week_index = round(days_week / 7, 2)

            # MOIS
            ops_month, days_month = _ops_and_days_in_range(ops_by_date, dates_set, month_start, today)
            ops_prev_month, _ = _ops_and_days_in_range(ops_by_date, dates_set, prev_month_start, prev_month_last_day)
            month_index = round(days_month / days_in_current_month, 2)

            # TOTAL
            sorted_dates = sorted(dates_set)
            if sorted_dates:
                first_day = date.fromisoformat(sorted_dates[0])
                total_span = max((today - first_day).days + 1, 1)
            else:
                total_span = 1
            total_active_days = len(dates_set)
            total_index = round(total_active_days / total_span, 2)

            # Statistiques par utilisateur
            indices = [day_index, week_index, month_index, total_index]
            moyenne = round(sum(indices) / 4, 2)
            variance = sum((x - moyenne) ** 2 for x in indices) / 4
            volatilite = round(variance ** 0.5, 2)
            stabilite = round(1 - volatilite, 2)

            # Score global pondéré pour le tri
            score_global = round(
                (day_index * 0.1) + (week_index * 0.3) + (month_index * 0.3) + (total_index * 0.3),
                2,
            )

            all_indices.append(moyenne)

            users_list.append({
                "user_id": uid,
                "display_name": display_names.get(uid, f"User {uid}"),
                "score_global": score_global,
                "statistics": {
                    "moyenne": moyenne,
                    "volatilite": volatilite,
                    "stabilite": stabilite,
                },
                "day": {
                    "index": day_index,
                    "trend": _trend(ops_today, ops_yesterday),
                    "operations_current": ops_today,
                    "operations_previous": ops_yesterday,
                },
                "week": {
                    "index": week_index,
                    "trend": _trend(ops_week, ops_prev_week),
                    "operations_current": ops_week,
                    "operations_previous": ops_prev_week,
                },
                "month": {
                    "index": month_index,
                    "trend": _trend(ops_month, ops_prev_month),
                    "operations_current": ops_month,
                    "operations_previous": ops_prev_month,
                },
                "total": {
                    "index": total_index,
                    "trend": "neutral",
                    "operations_current": total_ops,
                    "operations_previous": 0,
                },
            })

        # Trier par score_global DESC (meilleurs en premier)
        users_list.sort(key=lambda u: u["score_global"], reverse=True)

        # global_regularity : moyenne des indices moyens (variance inversée simplifiée)
        if all_indices:
            mean_idx = sum(all_indices) / len(all_indices)
            global_regularity = round(mean_idx, 2)
        else:
            global_regularity = 0.0

        logger.info(f"[REGULARITY] Users: {len(users_list)}, Global regularity: {global_regularity}")

        return {
            "global_regularity": global_regularity,
            "users": users_list,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[ADMIN ANALYTICS] Error in user-regularity-matrix: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur user-regularity-matrix: {e}")


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
