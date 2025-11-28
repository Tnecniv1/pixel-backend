# app/services/streak_service.py
"""
Service pour calculer les streaks d'entraînement des utilisateurs.
Basé sur la logique de l'endpoint /progression/regularite
"""

from datetime import datetime, timedelta, date
from collections import Counter
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def calculate_user_streak(user_id: int, supabase_client) -> Dict[str, Any]:
    """
    Calcule le streak actuel et le meilleur streak d'un utilisateur.
    
    Args:
        user_id: ID de l'utilisateur
        supabase_client: Client Supabase
    
    Returns:
        Dict avec:
        - current_streak: nombre de jours consécutifs jusqu'à aujourd'hui
        - best_streak: meilleur streak historique
        - last_training_date: dernière date d'entraînement (ISO format)
        - total_days: nombre total de jours avec entraînement
    """
    try:
        # 1) Récupérer tous les entraînements de l'utilisateur
        result = (
            supabase_client.table("Entrainement")
            .select("id, Date, date")
            .eq("Users_Id", user_id)
            .order("id")
            .limit(100000)
            .execute()
        )
        
        entrainements = getattr(result, "data", []) or []
        
        if not entrainements:
            return {
                "current_streak": 0,
                "best_streak": 0,
                "last_training_date": None,
                "total_days": 0
            }
        
        # 2) Extraire les dates
        dates_set = set()
        last_date = None
        
        for e in entrainements:
            date_str = e.get("Date") or e.get("date")
            if date_str:
                date_normalized = str(date_str)[:10]
                dates_set.add(date_normalized)
                
                try:
                    d = datetime.fromisoformat(date_normalized).date()
                    if last_date is None or d > last_date:
                        last_date = d
                except Exception:
                    pass
        
        if not dates_set:
            return {
                "current_streak": 0,
                "best_streak": 0,
                "last_training_date": None,
                "total_days": 0
            }
        
        # 3) Calculer le streak actuel
        today = date.today()
        current_streak = 0
        check_date = today
        
        while check_date.isoformat() in dates_set:
            current_streak += 1
            check_date -= timedelta(days=1)
        
        # 4) Calculer le meilleur streak historique
        sorted_dates = sorted([datetime.fromisoformat(d).date() for d in dates_set])
        
        best_streak = 0
        current_temp_streak = 1
        
        for i in range(1, len(sorted_dates)):
            diff = (sorted_dates[i] - sorted_dates[i-1]).days
            
            if diff == 1:
                current_temp_streak += 1
                best_streak = max(best_streak, current_temp_streak)
            else:
                current_temp_streak = 1
        
        best_streak = max(best_streak, current_temp_streak, current_streak)
        
        return {
            "current_streak": current_streak,
            "best_streak": best_streak,
            "last_training_date": last_date.isoformat() if last_date else None,
            "total_days": len(dates_set)
        }
        
    except Exception as e:
        logger.error(f"[StreakService] Erreur calcul streak pour user {user_id}: {e}")
        return {
            "current_streak": 0,
            "best_streak": 0,
            "last_training_date": None,
            "total_days": 0,
            "error": str(e)
        }


def get_streak_message(current_streak: int, best_streak: int) -> str:
    """
    Génère un message motivant basé sur le streak actuel.
    """
    if current_streak == 0:
        return "Commence un nouveau streak aujourd'hui ! 🎯"
    elif current_streak == 1:
        return "Premier jour ! Continue demain ! 💪"
    elif current_streak < 3:
        return f"Tu es à {current_streak} jours ! Continue ! 🔥"
    elif current_streak < 7:
        return f"Série de {current_streak} jours ! Tu es lancé ! 🚀"
    elif current_streak < 14:
        return f"Incroyable ! {current_streak} jours d'affilée ! ⭐"
    elif current_streak < 30:
        return f"Légendaire ! {current_streak} jours consécutifs ! 👑"
    else:
        return f"MONSTRE ! {current_streak} jours sans interruption ! 🏆"


def is_streak_at_risk(last_training_date: Optional[str]) -> bool:
    """
    Vérifie si le streak est en danger (pas d'entraînement aujourd'hui).
    """
    if not last_training_date:
        return True
    
    try:
        last_date = datetime.fromisoformat(last_training_date).date()
        today = date.today()
        return last_date < today
    except Exception:
        return True