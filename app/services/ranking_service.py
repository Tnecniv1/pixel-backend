# app/services/ranking_service.py
"""
Service pour détecter les changements de classement et envoyer des notifications.
"""

from typing import Optional, Dict, Any, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def check_ranking_changes(supabase_client) -> List[Dict[str, Any]]:
    """
    Vérifie tous les utilisateurs pour détecter les changements de classement.
    
    Returns:
        Liste des utilisateurs qui ont été dépassés avec leurs infos
    """
    changes = []
    
    try:
        # 1) Récupérer le classement actuel via la fonction SQL
        current_rankings = supabase_client.rpc('get_global_ranking').execute()
        
        if not current_rankings.data:
            logger.warning("[RankingService] Pas de données de classement")
            return []
        
        # 2) Préparer un dict user_id -> données actuelles
        current_by_user = {}
        for idx, row in enumerate(current_rankings.data, start=1):
            current_by_user[int(row['user_id'])] = {
                'rank': idx,
                'weighted_level': float(row['weighted_level']),
                'score_global': 0
            }
        
        # 3) Récupérer les classements précédents
        previous = supabase_client.table("Ranking_History").select(
            "user_id, rank, weighted_level"
        ).order("checked_at", desc=True).limit(1000).execute()
        
        previous_by_user = {}
        if previous.data:
            for row in previous.data:
                uid = int(row['user_id'])
                if uid not in previous_by_user:
                    previous_by_user[uid] = {
                        'rank': int(row['rank']),
                        'weighted_level': float(row['weighted_level'])
                    }
        
        # 4) Comparer et détecter les changements
        for user_id, current in current_by_user.items():
            previous = previous_by_user.get(user_id)
            
            if not previous:
                continue
            
            # Dépassement = le rang a AUGMENTÉ (1er -> 3e = dépassé)
            rank_diff = current['rank'] - previous['rank']
            
            if rank_diff > 0:
                changes.append({
                    'user_id': user_id,
                    'old_rank': previous['rank'],
                    'new_rank': current['rank'],
                    'positions_lost': rank_diff,
                    'old_level': previous['weighted_level'],
                    'new_level': current['weighted_level']
                })
                
                logger.info(
                    f"[RankingService] User {user_id} dépassé: "
                    f"{previous['rank']} -> {current['rank']} ({rank_diff} positions)"
                )
        
        # 5) Sauvegarder le classement actuel
        history_records = [
            {
                'user_id': uid,
                'rank': data['rank'],
                'score_global': data.get('score_global', 0),
                'weighted_level': data['weighted_level'],
                'checked_at': datetime.now().isoformat()
            }
            for uid, data in current_by_user.items()
        ]
        
        if history_records:
            try:
                supabase_client.table("Ranking_History").insert(history_records).execute()
                logger.info(f"[RankingService] {len(history_records)} classements sauvegardés")
            except Exception as e:
                logger.error(f"[RankingService] Erreur sauvegarde historique: {e}")
        
        return changes
        
    except Exception as e:
        logger.error(f"[RankingService] Erreur check_ranking_changes: {e}")
        return []


def get_ranking_change_message(old_rank: int, new_rank: int, positions_lost: int) -> Dict[str, str]:
    """
    Génère un message adapté selon l'ampleur du changement de classement.
    """
    if positions_lost == 1:
        return {
            "title": "⚡ Tu as été dépassé !",
            "body": f"Tu es passé de la {old_rank}e à la {new_rank}e place. Montre ce dont tu es capable ! 💪"
        }
    elif positions_lost <= 3:
        return {
            "title": "🔥 Attention au classement !",
            "body": f"Tu as perdu {positions_lost} places (#{old_rank} → #{new_rank}). Il est temps de réagir ! 🎯"
        }
    elif positions_lost <= 10:
        return {
            "title": "⚠️ Gros changement de classement !",
            "body": f"Tu as chuté de {positions_lost} places ! De la {old_rank}e à la {new_rank}e place. Remonte sur le podium ! 🚀"
        }
    else:
        return {
            "title": "🚨 Classement en danger !",
            "body": f"Attention ! Tu as perdu {positions_lost} places. Un entraînement s'impose ! 👊"
        }