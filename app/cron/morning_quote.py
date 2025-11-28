# app/cron/morning_quote.py
"""
Tâche planifiée : Envoi des phrases inspirantes du matin.
S'exécute tous les jours à 08:00 (heure de Paris).
"""

import logging
from datetime import datetime
from ..deps import service_client
from ..services.streak_service import calculate_user_streak
from ..services.morning_quotes import get_morning_quote_for_streak
from ..services.notification_service import send_push_notification

logger = logging.getLogger(__name__)


async def send_morning_quotes():
    """
    Envoie une phrase inspirante du matin à tous les utilisateurs qui ont:
    - Les notifications activées
    - morning_quote_enabled = true
    - Un token valide
    """
    logger.info("[MorningQuote] ☀️ Début de l'envoi des phrases du matin...")
    
    try:
        supabase = service_client()
        
        # 1) Récupérer tous les utilisateurs avec phrases du matin activées
        result = supabase.table("Users").select(
            "id, notification_token, notification_enabled, morning_quote_enabled"
        ).eq("notification_enabled", True).eq("morning_quote_enabled", True).execute()
        
        users = getattr(result, "data", []) or []
        logger.info(f"[MorningQuote] {len(users)} utilisateurs avec phrases activées")
        
        sent_count = 0
        skipped_count = 0
        
        for user in users:
            user_id = user.get("id")
            token = user.get("notification_token")
            
            if not token or not token.startswith("ExponentPushToken"):
                skipped_count += 1
                continue
            
            try:
                # 2) Calculer le streak pour personnaliser le message
                streak_data = calculate_user_streak(user_id, supabase)
                current_streak = streak_data.get("current_streak", 0)
                
                # 3) Obtenir une phrase adaptée au streak
                quote = get_morning_quote_for_streak(current_streak)
                
                # 4) Envoyer la notification
                success = await send_push_notification(
                    expo_token=token,
                    title=quote["title"],
                    body=quote["body"],
                    data={
                        "type": "morning_quote",
                        "current_streak": current_streak,
                        "timestamp": datetime.now().isoformat()
                    },
                    sound="default",
                    priority="default"
                )
                
                if success:
                    sent_count += 1
                    logger.debug(f"[MorningQuote] ✓ Phrase envoyée à user {user_id}")
                    
                    # Logger dans la DB
                    try:
                        supabase.table("Notification_Logs").insert({
                            "user_id": user_id,
                            "notification_type": "morning_quote",
                            "title": quote["title"],
                            "body": quote["body"],
                            "success": True
                        }).execute()
                    except Exception as log_error:
                        logger.warning(f"[MorningQuote] Erreur log DB: {log_error}")
                else:
                    logger.warning(f"[MorningQuote] ✗ Échec envoi pour user {user_id}")
                    
            except Exception as user_error:
                logger.error(f"[MorningQuote] Erreur pour user {user_id}: {user_error}")
                skipped_count += 1
                continue
        
        logger.info(
            f"[MorningQuote] ✅ Terminé: {sent_count} envoyées, "
            f"{skipped_count} ignorées sur {len(users)} utilisateurs"
        )
        
    except Exception as e:
        logger.error(f"[MorningQuote] ❌ Erreur globale: {e}")