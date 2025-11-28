# app/cron/ranking_checker.py
"""
Tâche planifiée : Vérification des changements de classement.
S'exécute toutes les 30 minutes pour détecter les dépassements.
"""

import logging
from datetime import datetime
from ..deps import service_client
from ..services.ranking_service import check_ranking_changes, get_ranking_change_message
from ..services.notification_service import send_push_notification

logger = logging.getLogger(__name__)


async def check_rankings():
    """
    Vérifie les changements de classement et notifie les utilisateurs dépassés.
    """
    logger.info("[RankingChecker] 📊 Début de la vérification des classements...")
    
    try:
        supabase = service_client()
        
        # 1) Détecter les changements de classement
        changes = await check_ranking_changes(supabase)
        
        if not changes:
            logger.info("[RankingChecker] Aucun changement de classement détecté")
            return
        
        logger.info(f"[RankingChecker] {len(changes)} utilisateurs dépassés détectés")
        
        sent_count = 0
        skipped_count = 0
        
        for change in changes:
            user_id = change['user_id']
            old_rank = change['old_rank']
            new_rank = change['new_rank']
            positions_lost = change['positions_lost']
            
            try:
                # 2) Récupérer le token de l'utilisateur
                user_result = supabase.table("Users").select(
                    "notification_token, notification_enabled"
                ).eq("id", user_id).single().execute()
                
                if not user_result.data:
                    logger.debug(f"[RankingChecker] User {user_id} non trouvé")
                    skipped_count += 1
                    continue
                
                user_data = user_result.data
                
                # Vérifier si les notifications sont activées
                if not user_data.get("notification_enabled", False):
                    logger.debug(f"[RankingChecker] Notifications désactivées pour user {user_id}")
                    skipped_count += 1
                    continue
                
                token = user_data.get("notification_token")
                if not token or not token.startswith("ExponentPushToken"):
                    logger.debug(f"[RankingChecker] Token invalide pour user {user_id}")
                    skipped_count += 1
                    continue
                
                # 3) Générer le message adapté
                message = get_ranking_change_message(old_rank, new_rank, positions_lost)
                
                # 4) Envoyer la notification
                success = await send_push_notification(
                    expo_token=token,
                    title=message["title"],
                    body=message["body"],
                    data={
                        "type": "ranking_change",
                        "old_rank": old_rank,
                        "new_rank": new_rank,
                        "positions_lost": positions_lost,
                        "timestamp": datetime.now().isoformat()
                    },
                    sound="default",
                    priority="high"
                )
                
                if success:
                    sent_count += 1
                    logger.info(
                        f"[RankingChecker] ✓ Notification envoyée à user {user_id} "
                        f"(#{old_rank} → #{new_rank})"
                    )
                    
                    # Logger dans la DB
                    try:
                        supabase.table("Notification_Logs").insert({
                            "user_id": user_id,
                            "notification_type": "ranking_change",
                            "title": message["title"],
                            "body": message["body"],
                            "success": True
                        }).execute()
                    except Exception as log_error:
                        logger.warning(f"[RankingChecker] Erreur log DB: {log_error}")
                else:
                    logger.warning(f"[RankingChecker] ✗ Échec envoi pour user {user_id}")
                    
            except Exception as user_error:
                logger.error(f"[RankingChecker] Erreur pour user {user_id}: {user_error}")
                skipped_count += 1
                continue
        
        logger.info(
            f"[RankingChecker] ✅ Terminé: {sent_count} notifications envoyées, "
            f"{skipped_count} ignorées sur {len(changes)} changements"
        )
        
    except Exception as e:
        logger.error(f"[RankingChecker] ❌ Erreur globale: {e}")