from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from ..services.notification_service import send_push_notification, send_push_notifications_bulk
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

class ChatMessageNotificationRequest(BaseModel):
    sender_id: int
    sender_name: str
    message_content: str
    message_id: Optional[str] = None

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


@router.post("/chat-message")
async def notify_chat_message(request: ChatMessageNotificationRequest):
    """
    Envoie une notification push a tous les utilisateurs (sauf l'expediteur)
    quand un nouveau message est poste dans le chat global.
    """
    try:
        supabase = service_client()

        # Recuperer le token de l'expediteur pour l'exclure par token (pas seulement par ID)
        sender_response = supabase.table("Users").select(
            "notification_token"
        ).eq("id", request.sender_id).single().execute()

        sender_token = None
        if sender_response.data:
            sender_token = sender_response.data.get("notification_token")

        # Recuperer tous les utilisateurs avec notifications activees (sauf l'expediteur)
        response = supabase.table("Users").select(
            "id, notification_token, notification_enabled"
        ).neq("id", request.sender_id).execute()

        if not response.data:
            logger.info("[ChatNotif] Aucun utilisateur a notifier")
            return {"success": True, "notified": 0, "message": "Aucun utilisateur"}

        # Filtrer les utilisateurs avec notifications activees et token valide
        # + exclure le token de l'expediteur (corrige l'auto-notification)
        users_to_notify = [
            user for user in response.data
            if user.get("notification_enabled", False)
            and user.get("notification_token")
            and user["notification_token"].startswith("ExponentPushToken")
            and user["notification_token"] != sender_token
        ]

        if not users_to_notify:
            logger.info("[ChatNotif] Aucun utilisateur avec notifications activees")
            return {"success": True, "notified": 0, "message": "Aucun token valide"}

        # Dedupliquer par token (evite les notifications en double sur un meme appareil)
        seen_tokens = set()
        unique_users = []
        for user in users_to_notify:
            token = user["notification_token"]
            if token not in seen_tokens:
                seen_tokens.add(token)
                unique_users.append(user)

        # Preparer le contenu de la notification
        content_preview = request.message_content[:100] + "..." if len(request.message_content) > 100 else request.message_content

        # Preparer les messages en bulk (un seul par token unique)
        messages = [
            {
                "token": user["notification_token"],
                "title": f"💬 {request.sender_name}",
                "body": content_preview,
                "data": {
                    "type": "chat_message",
                    "sender_id": request.sender_id,
                    "sender_name": request.sender_name,
                    "message_id": request.message_id
                }
            }
            for user in unique_users
        ]

        # Envoyer en batch
        result = await send_push_notifications_bulk(messages)

        logger.info(f"[ChatNotif] Envoye: {result['success']} succes, {result['failed']} echecs sur {len(users_to_notify)} utilisateurs")

        return {
            "success": True,
            "notified": result["success"],
            "failed": result["failed"],
            "total_eligible": len(users_to_notify)
        }

    except Exception as e:
        logger.error(f"[ChatNotif] Erreur: {e}")
        raise HTTPException(status_code=500, detail=str(e))