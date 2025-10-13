from typing import Optional
try:
    # supabase-py v2 (sync)
    from supabase._sync.client import SyncClient as SupabaseClient
except Exception:
    SupabaseClient = object  # fallback neutre si l'import change à l'avenir

def resolve_or_register_user_id(
    supabase: SupabaseClient,
    auth_uid: str,
    email: Optional[str] = None,
) -> int:
    # même contenu que ci-dessus…
    m = supabase.table("users_map").select("*").eq("auth_uid", auth_uid).execute()
    data = getattr(m, "data", []) or []
    if data:
        return int(data[0]["user_id"])

    new_user = {"name": email or "Utilisateur", "email": email or None}
    u = supabase.table("Users").insert(new_user).execute()
    udata = getattr(u, "data", []) or []
    if not udata:
        raise RuntimeError("Création Users échouée")
    user_id = int(udata[0]["id"])

    supabase.table("users_map").insert({
        "auth_uid": auth_uid,
        "user_id": user_id,
    }).execute()

    return user_id
