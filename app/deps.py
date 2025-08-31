# app/deps.py
import os, json, base64
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")

# Client global service (ne jamais l'auth() avec un JWT user)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def service_client() -> Client:
    """Client service tout neuf (zéro état, pas de JWT collant)."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def _b64url_decode(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.encode("utf-8"))

def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()

def get_auth_uid_from_bearer(authorization: Optional[str]) -> Optional[str]:
    token = _extract_bearer(authorization)
    if not token:
        return None
    try:
        payload = json.loads(_b64url_decode(token.split(".")[1]).decode("utf-8"))
        return payload.get("sub")
    except Exception:
        return None

def user_scoped_client(authorization: Optional[str]) -> Client:
    """Client jetable scoppé utilisateur pour CETTE requête (RLS via auth.uid())."""
    token = _extract_bearer(authorization)
    if not token:
        raise ValueError("Missing Bearer token")
    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    sb.postgrest.auth(token)  # active RLS avec le JWT utilisateur
    return sb
