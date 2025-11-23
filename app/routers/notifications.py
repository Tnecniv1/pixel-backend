from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from ..services.notification_service import send_push_notification
from ..deps import service_client
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])

class SendNotificationRequest(BaseModel):
    user_id: int
    title: str
    body: str
    data: Optional[Dict[str, Any]] = None
    sound: str = "default"
    priority: str = "high"

class TestNotificationRequest(BaseModel):
    expo_token: str
    title: str = "🔔 Test Notification"
    body: str = "Ceci est un test depuis le backend !"

@router.post("/send")
async def send_notification_to_user(request: SendNotificationRequest):
    """
    Envoie une notification push à un utilisateur spécifique
    """
    try:
        supabase = service_client()
        
        # Récupérer le token de l'utilisateur
        response = supabase.table("Users").select("notification_token, notification_enabled").eq("id", request.user_id).single().execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        
        user_data = response.data
        
        if not user_data.get("notification_enabled", False):
            return {"success": False, "message": "Notifications désactivées pour cet utilisateur"}
        
        token = user_data.get("notification_token")
        if not token:
            return {"success": False, "message": "Pas de token de notification"}
        
        # Envoyer la notification
        success = await send_push_notification(
            expo_token=token,
            title=request.title,
            body=request.body,
            data=request.data,
            sound=request.sound,
            priority=request.priority
        )
        
        if success:
            return {"success": True, "message": "Notification envoyée"}
        else:
            raise HTTPException(status_code=500, detail="Erreur lors de l'envoi")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur send_notification_to_user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def test_notification(request: TestNotificationRequest):
    """
    Endpoint de test pour envoyer une notification directement avec un token
    """
    try:
        success = await send_push_notification(
            expo_token=request.expo_token,
            title=request.title,
            body=request.body,
            data={"type": "test"}
        )
        
        if success:
            return {"success": True, "message": "Notification de test envoyée"}
        else:
            raise HTTPException(status_code=500, detail="Erreur lors de l'envoi")
            
    except Exception as e:
        logger.error(f"Erreur test_notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))