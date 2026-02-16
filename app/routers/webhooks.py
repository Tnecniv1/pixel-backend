# app/routers/webhooks.py
"""
Webhook RevenueCat pour synchroniser le statut d'abonnement dans users_map.
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request

from app.deps import service_client

logger = logging.getLogger(__name__)

REVENUECAT_WEBHOOK_SECRET = os.getenv("REVENUECAT_WEBHOOK_SECRET", "")

webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Événements qui activent l'abonnement
SUBSCRIBE_EVENTS = {"INITIAL_PURCHASE", "RENEWAL", "UNCANCELLATION"}
# Événements qui désactivent l'abonnement
UNSUBSCRIBE_EVENTS = {"EXPIRATION", "CANCELLATION"}


def _verify_webhook_secret(authorization: Optional[str]) -> None:
    if not REVENUECAT_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="REVENUECAT_WEBHOOK_SECRET non configuré")
    token = ""
    if authorization:
        token = authorization.split(" ", 1)[1] if " " in authorization else authorization
    if token != REVENUECAT_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Webhook secret invalide")


@webhook_router.post("/revenuecat")
async def revenuecat_webhook(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    _verify_webhook_secret(authorization)

    body = await request.json()
    event = body.get("event", {})
    event_type = event.get("type", "")
    app_user_id = event.get("app_user_id", "")

    if not app_user_id:
        logger.warning("[REVENUECAT] Événement sans app_user_id: %s", event_type)
        return {"ok": True, "skipped": True}

    if event_type in SUBSCRIBE_EVENTS:
        is_subscribed = True
    elif event_type in UNSUBSCRIBE_EVENTS:
        is_subscribed = False
    else:
        logger.info("[REVENUECAT] Événement ignoré: %s", event_type)
        return {"ok": True, "skipped": True}

    sb = service_client()
    try:
        sb.table("users_map").update(
            {"is_subscribed": is_subscribed}
        ).eq("auth_uid", app_user_id).execute()

        logger.info(
            "[REVENUECAT] %s → is_subscribed=%s pour auth_uid=%s",
            event_type, is_subscribed, app_user_id,
        )
    except Exception as e:
        logger.error("[REVENUECAT] Erreur mise à jour: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return {"ok": True, "event_type": event_type, "is_subscribed": is_subscribed}
