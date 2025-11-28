# app/routers/notification_settings.py
"""
Router pour gérer les paramètres de notifications des utilisateurs.
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from datetime import time
from ..deps import service_client
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notification-settings", tags=["notifications"])


class NotificationSettings(BaseModel):
    notification_enabled: Optional[bool] = None
    morning_quote_enabled: Optional[bool] = None
    notification_time: Optional[str] = None  # Format: "HH:MM" (ex: "20:00")


class NotificationSettingsResponse(BaseModel):
    notification_enabled: bool
    morning_quote_enabled: bool
    notification_time: str
    notification_token: Optional[str]


def _get_user_id_from_bearer(authorization: Optional[str]) -> Optional[int]:
    """Résout Users_Id depuis le JWT."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    jwt = authorization.split(" ", 1)[1]
    try:
        supabase = service_client()
        u = supabase.auth.get_user(jwt)
        user_obj = getattr(u, "user", None) or u
        auth_uid = user_obj.id
        m = supabase.table("users_map").select("user_id").eq("auth_uid", auth_uid).maybe_single().execute()
        data = getattr(m, "data", None)
        return int(data["user_id"]) if data and "user_id" in data else None
    except Exception as e:
        logger.error(f"Erreur résolution user_id: {e}")
        return None


@router.get("", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    authorization: Optional[str] = Header(None)
):
    """
    Récupère les paramètres de notification de l'utilisateur connecté.
    """
    user_id = _get_user_id_from_bearer(authorization)
    
    if user_id is None:
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    try:
        supabase = service_client()
        
        result = supabase.table("Users").select(
            "notification_enabled, morning_quote_enabled, notification_time, notification_token"
        ).eq("id", user_id).single().execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        
        data = result.data
        
        # Convertir le time en string HH:MM
        notif_time = data.get("notification_time")
        if isinstance(notif_time, time):
            time_str = notif_time.strftime("%H:%M")
        else:
            time_str = str(notif_time) if notif_time else "20:00"
        
        return NotificationSettingsResponse(
            notification_enabled=data.get("notification_enabled", True),
            morning_quote_enabled=data.get("morning_quote_enabled", True),
            notification_time=time_str,
            notification_token=data.get("notification_token")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur get_notification_settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("")
async def update_notification_settings(
    settings: NotificationSettings,
    authorization: Optional[str] = Header(None)
):
    """
    Met à jour les paramètres de notification de l'utilisateur connecté.
    """
    user_id = _get_user_id_from_bearer(authorization)
    
    if user_id is None:
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    try:
        supabase = service_client()
        
        # Construire l'objet de mise à jour
        updates = {}
        
        if settings.notification_enabled is not None:
            updates["notification_enabled"] = settings.notification_enabled
        
        if settings.morning_quote_enabled is not None:
            updates["morning_quote_enabled"] = settings.morning_quote_enabled
        
        if settings.notification_time is not None:
            # Valider le format HH:MM
            try:
                hour, minute = settings.notification_time.split(":")
                hour_int = int(hour)
                minute_int = int(minute)
                
                if not (0 <= hour_int <= 23 and 0 <= minute_int <= 59):
                    raise ValueError("Heure invalide")
                
                updates["notification_time"] = settings.notification_time
            except Exception as e:
                raise HTTPException(
                    status_code=400, 
                    detail="Format d'heure invalide. Utilisez HH:MM (ex: 20:00)"
                )
        
        if not updates:
            raise HTTPException(status_code=400, detail="Aucun paramètre à mettre à jour")
        
        # Mettre à jour dans la base
        result = supabase.table("Users").update(updates).eq("id", user_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        
        logger.info(f"Paramètres de notification mis à jour pour user {user_id}: {updates}")
        
        return {
            "success": True,
            "message": "Paramètres mis à jour",
            "updated": updates
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur update_notification_settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-notification")
async def send_test_notification(
    authorization: Optional[str] = Header(None)
):
    """
    Envoie une notification de test à l'utilisateur connecté.
    """
    user_id = _get_user_id_from_bearer(authorization)
    
    if user_id is None:
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    try:
        supabase = service_client()
        
        # Récupérer le token
        result = supabase.table("Users").select(
            "notification_token"
        ).eq("id", user_id).single().execute()
        
        if not result.data or not result.data.get("notification_token"):
            raise HTTPException(status_code=400, detail="Token de notification non enregistré")
        
        token = result.data["notification_token"]
        
        # Envoyer une notification de test
        from ..services.notification_service import send_push_notification
        
        success = await send_push_notification(
            expo_token=token,
            title="🧪 Notification de test",
            body="Tes notifications fonctionnent parfaitement ! 🎉",
            data={"type": "test"},
            sound="default",
            priority="high"
        )
        
        if success:
            return {"success": True, "message": "Notification de test envoyée"}
        else:
            raise HTTPException(status_code=500, detail="Échec de l'envoi")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur send_test_notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))