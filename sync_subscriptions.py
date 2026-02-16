import os
import sys
import json
import time
from typing import Any, Dict, Optional

import requests
from supabase import create_client


# -----------------------------
# Required environment variables
# -----------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
REVENUECAT_SECRET_API_KEY = os.environ.get("REVENUECAT_SECRET_API_KEY")
REVENUECAT_PROJECT_ID = os.environ.get("REVENUECAT_PROJECT_ID")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
    sys.exit(1)

if not REVENUECAT_SECRET_API_KEY:
    print("Missing REVENUECAT_SECRET_API_KEY", file=sys.stderr)
    sys.exit(1)

if not REVENUECAT_PROJECT_ID:
    print("Missing REVENUECAT_PROJECT_ID (find it in RevenueCat dashboard URL / project settings)", file=sys.stderr)
    sys.exit(1)


# RevenueCat API v2 base
RC_V2_BASE = "https://api.revenuecat.com/v2"


def rc_headers() -> Dict[str, str]:
    # RevenueCat v2 expects Bearer auth with the secret key
    return {"Authorization": f"Bearer {REVENUECAT_SECRET_API_KEY}"}


def fetch_active_entitlements(customer_id: str, timeout_s: int = 20) -> Dict[str, Any]:
    """
    GET /v2/projects/{project_id}/customers/{customer_id}/active_entitlements
    Returns a list object with 'items' containing active entitlements.
    """
    url = f"{RC_V2_BASE}/projects/{REVENUECAT_PROJECT_ID}/customers/{customer_id}/active_entitlements"
    r = requests.get(url, headers=rc_headers(), timeout=timeout_s)

    if r.status_code == 404:
        # Customer not found in RevenueCat
        return {}

    r.raise_for_status()
    return r.json()


def is_subscribed_from_active_entitlements(payload: Dict[str, Any]) -> bool:
    """
    RevenueCat active_entitlements endpoint returns:
      { "items": [ ... ] }
    If items is non-empty => at least one entitlement is active => subscribed.
    """
    if not payload:
        return False
    items = payload.get("items")
    return bool(items) and isinstance(items, list)


def main() -> None:
    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    # Read users
    res = sb.table("users_map").select("auth_uid,is_subscribed").execute()
    rows = res.data or []
    print(f"Users trouvés: {len(rows)}")

    updated = 0
    unchanged = 0
    errors = 0
    not_found = 0

    # Simple rate-limit safety (avoid hammering)
    # Adjust if you have many users.
    sleep_s = 0.10

    for row in rows:
        auth_uid = row.get("auth_uid")
        if not auth_uid:
            continue

        try:
            payload = fetch_active_entitlements(auth_uid)
            if payload == {}:
                # 404 or empty response treated as not subscribed
                active = False
                # track "not found" only if truly not found; our fetch returns {} for 404
                # but could also be empty. We'll keep it as not_found to be explicit.
                not_found += 1
            else:
                active = is_subscribed_from_active_entitlements(payload)

            current = bool(row.get("is_subscribed"))
            if current == active:
                unchanged += 1
            else:
                sb.table("users_map").update({"is_subscribed": active}).eq("auth_uid", auth_uid).execute()
                updated += 1
                print(f"OK auth_uid={auth_uid} -> is_subscribed={active}")

        except requests.HTTPError as e:
            errors += 1
            status = getattr(e.response, "status_code", "unknown")
            print(f"ERR auth_uid={auth_uid}: HTTP {status} {e}", file=sys.stderr)
        except Exception as e:
            errors += 1
            print(f"ERR auth_uid={auth_uid}: {e}", file=sys.stderr)

        time.sleep(sleep_s)

    print(json.dumps(
        {"updated": updated, "unchanged": unchanged, "not_found": not_found, "errors": errors},
        indent=2
    ))


if __name__ == "__main__":
    main()
