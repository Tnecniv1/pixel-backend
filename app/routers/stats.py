from __future__ import annotations

import os
from functools import lru_cache
from datetime import datetime, timedelta, date as date_cls
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException, Query
from supabase import create_client, Client

router = APIRouter(prefix="/stats", tags=["stats"])
PARIS = ZoneInfo("Europe/Paris")

# ────────────────────────────────────────────────────────────────────────────────
# Supabase client (cached)
# ────────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _sb() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_*_KEY")
    return create_client(url, key)

# ────────────────────────────────────────────────────────────────────────────────
# Health
# ────────────────────────────────────────────────────────────────────────────────
@router.get("/ping")
def ping():
    return {"ok": True}

# ────────────────────────────────────────────────────────────────────────────────
# Small helper: try users_map in both flavors (Users_Id | user_id)
# ────────────────────────────────────────────────────────────────────────────────
def _users_map_lookup(sb: Client, auth_uid: str) -> int | None:
    # try Users_Id (CamelCase)
    try:
        r = (
            sb.table("users_map")
              .select("Users_Id")
              .eq("auth_uid", auth_uid)
              .single()
              .execute()
        )
        if r.data and "Users_Id" in r.data:
            return int(r.data["Users_Id"])
    except Exception:
        pass
    # try user_id (snake_case)
    try:
        r = (
            sb.table("users_map")
              .select("user_id")
              .eq("auth_uid", auth_uid)
              .single()
              .execute()
        )
        if r.data and "user_id" in r.data:
            return int(r.data["user_id"])
    except Exception:
        pass
    return None

# ────────────────────────────────────────────────────────────────────────────────
# Resolve current user → Users.id (int)
# ────────────────────────────────────────────────────────────────────────────────
def _resolve_user(
    authorization: str | None,
    users_id_override: str | None = None,
    auth_uid_override: str | None = None,
    email_override: str | None = None,
) -> int:
    """
    Returns Users.id (int) preferring, in order:
      1) users_id_override (stringified int)
      2) auth_uid_override (UUID) → users_map / Users.auth_uid
      3) email_override → Users.email
      4) Authorization: Bearer <jwt> → users_map / Users.auth_uid / fallback by token email
    """
    sb = _sb()

    # 1) direct override Users.id
    if users_id_override:
        try:
            return int(users_id_override)
        except ValueError:
            auth_uid_override = users_id_override  # if not int, treat as auth_uid below

    auth_uid = auth_uid_override
    auth_email = (email_override or "").lower() if email_override else None

    # 2) no overrides → read identity from JWT
    if not auth_uid and not auth_email:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        token = authorization.split(" ", 1)[1]
        try:
            u = sb.auth.get_user(token).user
            if not u:
                raise HTTPException(status_code=401, detail="Invalid token")
            auth_uid = u.id
            auth_email = (u.email or "").lower()
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")

    # 3) users_map(auth_uid → Users.id), supports Users_Id or user_id
    if auth_uid:
        mapped = _users_map_lookup(sb, auth_uid)
        if mapped is not None:
            return mapped

        # 4) Users.auth_uid = auth_uid
        try:
            r2 = (
                sb.table("Users")
                  .select("id")
                  .eq("auth_uid", auth_uid)
                  .single()
                  .execute()
            )
            if r2.data and "id" in r2.data:
                return int(r2.data["id"])
        except Exception:
            pass

    # 5) Fallback by Users.email (lowercased)
    if auth_email:
        try:
            r3 = (
                sb.table("Users")
                  .select("id")
                  .ilike("email", auth_email)
                  .single()
                  .execute()
            )
            if r3.data and "id" in r3.data:
                return int(r3.data["id"])
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="User mapping not found")

# ────────────────────────────────────────────────────────────────────────────────
# Day streak (global — all operations)
# ────────────────────────────────────────────────────────────────────────────────
@router.get("/day_streak_current")
def day_streak_current(
    # capture Authorization header safely
    authorization: str | None = Header(None, alias="Authorization"),
    # debug params to test without header
    token: str | None = Query(None, description="JWT if Authorization header isn't sent"),
    users_id: str | None = Query(None, description="Override Users.id (int)"),
    auth_uid: str | None = Query(None, description="Override auth_uid (UUID)"),
    email: str | None = Query(None, description="Override Users.email"),
):
    sb = _sb()

    # fallback: build Bearer from ?token=
    if (not authorization or not authorization.startswith("Bearer ")) and token:
        authorization = f"Bearer {token}"

    uid = _resolve_user(
        authorization,
        users_id_override=users_id,
        auth_uid_override=auth_uid,
        email_override=email,
    )

    # pull last 2 years of training dates
    since = (datetime.now(PARIS) - timedelta(days=730)).date().isoformat()
    res = (
        sb.table("Entrainement")
        .select("Date")
        .eq("Users_Id", uid)
        .gte("Date", since)
        .order("Date", desc=False)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return {"current_streak_days": 0, "max_streak_days": 0}

    # distinct training days
    days: set[date_cls] = set()
    for r in rows:
        d = r["Date"]
        if isinstance(d, str):
            d = datetime.fromisoformat(d).date()
        days.add(d)

    # current streak (ending today in Europe/Paris)
    today = datetime.now(PARIS).date()
    cur = 0
    probe = today
    while probe in days:
        cur += 1
        probe = probe - timedelta(days=1)

    # max streak (gaps & islands)
    ds = sorted(days)
    mx, run, prev = 0, 0, None
    for d in ds:
        if prev is None or d == prev + timedelta(days=1):
            run += 1
        else:
            mx = max(mx, run)
            run = 1
        prev = d
    mx = max(mx, run)

    return {"current_streak_days": cur, "max_streak_days": mx}

# ────────────────────────────────────────────────────────────────────────────────
# Debug helpers
# ────────────────────────────────────────────────────────────────────────────────
@router.get("/echo")
def echo(
    authorization: str | None = Header(None, alias="Authorization"),
    token: str | None = Query(None),
):
    # Show exactly what FastAPI receives (quick sanity check)
    return {
        "loaded_from": __file__,
        "authorization_header": authorization,
        "query_token": token,
        "env_SUPABASE_URL": bool(os.environ.get("SUPABASE_URL")),
        "env_SERVICE_ROLE": bool(os.environ.get("SUPABASE_SERVICE_ROLE_KEY")),
    }

@router.get("/debug_user")
def debug_user(
    authorization: str | None = Header(None, alias="Authorization"),
    token: str | None = Query(None),
):
    sb = _sb()

    # build Bearer from ?token= if header is missing
    if (not authorization or not authorization.startswith("Bearer ")) and token:
        authorization = f"Bearer {token}"
    if not authorization or not authorization.startswith("Bearer "):
        return {"error": "Missing Bearer"}

    jwt = authorization.split(" ", 1)[1]
    out = {"token_info": {}, "lookups": {}}

    # token info
    try:
        u = sb.auth.get_user(jwt).user
        out["token_info"] = {"auth_uid": getattr(u, "id", None), "email": getattr(u, "email", None)}
    except Exception as e:
        out["token_info"] = {"error": f"auth.get_user failed: {e}"}
        return out

    auth_uid = out["token_info"].get("auth_uid")
    email_lc = (out["token_info"].get("email") or "").lower()

    # users_map (both column variants)
    try:
        mapped = _users_map_lookup(sb, auth_uid)
        out["lookups"]["users_map"] = {"mapped_user_id": mapped}
    except Exception as e:
        out["lookups"]["users_map"] = f"error: {e}"

    # Users.auth_uid
    try:
        r = sb.table("Users").select("id").eq("auth_uid", auth_uid).single().execute()
        out["lookups"]["Users.auth_uid"] = r.data
    except Exception as e:
        out["lookups"]["Users.auth_uid"] = f"error: {e}"

    # Users.email
    try:
        r = sb.table("Users").select("id").ilike("email", email_lc).single().execute()
        out["lookups"]["Users.email"] = r.data
    except Exception as e:
        out["lookups"]["Users.email"] = f"error: {e}"

    return out