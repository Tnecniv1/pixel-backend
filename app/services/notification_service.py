import httpx
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

async def send_push_notification(
    expo_token: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
    sound: str = "default",
    priority: str = "high"
) -> bool:
    """
    Envoie une notification push via Expo
    
    Args:
        expo_token: Token Expo du destinataire (ExponentPushToken[...])
        title: Titre de la notification
        body: Corps de la notification
        data: Données additionnelles (optionnel)
        sound: Son de la notification
        priority: Priorité (high, normal, default)
    
    Returns:
        True si envoyé avec succès, False sinon
    """
    
    if not expo_token or not expo_token.startswith("ExponentPushToken"):
        logger.error(f"Token invalide: {expo_token}")
        return False
    
    message = {
        "to": expo_token,
        "sound": sound,
        "title": title,
        "body": body,
        "priority": priority,
    }
    
    if data:
        message["data"] = data
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                EXPO_PUSH_URL,
                json=message,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Notification envoyée: {result}")
                
                # Vérifier les erreurs Expo
                if "data" in result and len(result["data"]) > 0:
                    first_result = result["data"][0]
                    if first_result.get("status") == "error":
                        logger.error(f"Erreur Expo: {first_result.get('message')}")
                        return False
                
                return True
            else:
                logger.error(f"Erreur HTTP {response.status_code}: {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"Erreur envoi notification: {e}")
        return False


async def send_push_notifications_bulk(
    tokens_with_messages: List[Dict[str, Any]]
) -> Dict[str, int]:
    """
    Envoie plusieurs notifications en batch
    
    Args:
        tokens_with_messages: Liste de dicts avec {token, title, body, data}
    
    Returns:
        Dict avec {success: count, failed: count}
    """
    
    messages = []
    for item in tokens_with_messages:
        token = item.get("token")
        if not token or not token.startswith("ExponentPushToken"):
            continue
            
        messages.append({
            "to": token,
            "sound": item.get("sound", "default"),
            "title": item.get("title"),
            "body": item.get("body"),
            "priority": item.get("priority", "high"),
            "data": item.get("data", {}),
        })
    
    if not messages:
        return {"success": 0, "failed": 0}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                EXPO_PUSH_URL,
                json=messages,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                success_count = sum(
                    1 for r in result.get("data", []) 
                    if r.get("status") == "ok"
                )
                failed_count = len(messages) - success_count
                
                logger.info(f"Batch envoyé: {success_count} succès, {failed_count} échecs")
                return {"success": success_count, "failed": failed_count}
            else:
                logger.error(f"Erreur HTTP {response.status_code}")
                return {"success": 0, "failed": len(messages)}
                
    except Exception as e:
        logger.error(f"Erreur batch: {e}")
        return {"success": 0, "failed": len(messages)}