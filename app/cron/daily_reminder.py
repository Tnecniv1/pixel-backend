# app/cron/daily_reminder.py
"""
Tâche planifiée : Envoi des rappels quotidiens d'entraînement.
S'exécute tous les jours à 20:00 (heure de Paris).
"""

import logging
from datetime import datetime
from ..deps import service_client
from ..services.streak_service import calculate_user_streak, is_streak_at_risk
from ..services.notification_service import send_push_notification

logger = logging.getLogger(__name__)


async def send_daily_reminders():
    """
    Envoie un rappel quotidien à tous les utilisateurs qui ont:
    - Les notifications activées
    - Un token valide
    - Pas encore fait leur entraînement du jour
    """
    logger.info("[DailyReminder] 🔔 Début de l'envoi des rappels quotidiens...")
    
    try:
        supabase = service_client()
        
        # 1) Récupérer tous les utilisateurs avec notifications activées
        result = supabase.table("Users").select(
            "id, notification_token, notification_enabled"
        ).eq("notification_enabled", True).execute()
        
        users = getattr(result, "data", []) or []
        logger.info(f"[DailyReminder] {len(users)} utilisateurs avec notifications activées")
        
        sent_count = 0
        skipped_count = 0
        
        for user in users:
            user_id = user.get("id")
            token = user.get("notification_token")
            
            if not token or not token.startswith("ExponentPushToken"):
                skipped_count += 1
                continue
            
            try:
                # 2) Calculer le streak de l'utilisateur
                streak_data = calculate_user_streak(user_id, supabase)
                current_streak = streak_data.get("current_streak", 0)
                last_training = streak_data.get("last_training_date")
                
                # 3) Vérifier si l'utilisateur a déjà fait son entraînement aujourd'hui
                if not is_streak_at_risk(last_training):
                    logger.debug(f"[DailyReminder] User {user_id} déjà entraîné aujourd'hui, skip")
                    skipped_count += 1
                    continue
                
                # 4) Construire le message selon le streak
                if current_streak == 0:
                    title = "🎯 Entraîne-toi !"
                    body = "Lance ton streak aujourd'hui !"
                elif current_streak == 1:
                    title = "🔥 Ne casse pas !"
                    body = "1 jour de streak. Continue !"
                else:
                    title = f"🔥 {current_streak} jours !"
                    body = f"Garde ta série de {current_streak} jours !"
                
                # 5) Envoyer la notification
                success = await send_push_notification(
                    expo_token=token,
                    title=title,
                    body=body,
                    data={
                        "type": "daily_reminder",
                        "current_streak": current_streak,
                        "timestamp": datetime.now().isoformat()
                    },
                    sound="default",
                    priority="high"
                )
                
                if success:
                    sent_count += 1
                    logger.debug(f"[DailyReminder] ✓ Notification envoyée à user {user_id}")
                    
                    # Logger dans la DB
                    try:
                        supabase.table("Notification_Logs").insert({
                            "user_id": user_id,
                            "notification_type": "daily_reminder",
                            "title": title,
                            "body": body,
                            "success": True
                        }).execute()
                    except Exception as log_error:
                        logger.warning(f"[DailyReminder] Erreur log DB: {log_error}")
                else:
                    logger.warning(f"[DailyReminder] ✗ Échec envoi pour user {user_id}")
                    
            except Exception as user_error:
                logger.error(f"[DailyReminder] Erreur pour user {user_id}: {user_error}")
                skipped_count += 1
                continue
        
        logger.info(
            f"[DailyReminder] ✅ Terminé: {sent_count} envoyées, "
            f"{skipped_count} ignorées sur {len(users)} utilisateurs"
        )
        
    except Exception as e:
        logger.error(f"[DailyReminder] ❌ Erreur globale: {e}")