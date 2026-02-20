import numpy as np
from datetime import date
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# FEATURE FLAG
# ─────────────────────────────────────────────
import os
USE_NEW_SCORING = os.getenv("USE_NEW_SCORING", "False") == "True"


# ─────────────────────────────────────────────
# RÉCUPÉRATION HISTORIQUE
# ─────────────────────────────────────────────
def get_user_stats_for_operation(sb, user_id: int, operation_type: str, niveau: int, limit: int = 50):
    """
    Récupère les 50 dernières observations du même type/niveau
    pour calculer moyenne et écart-type de vitesse et marge d'erreur.
    """
    try:
        res = sb.table("Observations")\
            .select("Temps_Seconds, Marge_Erreur, Etat")\
            .eq("Users_Id", user_id)\
            .eq("Operation", operation_type)\
            .eq("Niveau", niveau)\
            .order("id", desc=True)\
            .limit(limit)\
            .execute()

        data = res.data if res.data else []
        logger.info(f"[SCORING] Historical data for user {user_id}, op {operation_type}, niveau {niveau}: {len(data)} entries")
        return data
    except Exception as e:
        logger.error(f"[SCORING] Error fetching historical data: {e}")
        return []


# ─────────────────────────────────────────────
# CALCUL VITESSE
# ─────────────────────────────────────────────
def calculate_vitesse_score(
    etat: str,
    temps_seconds: float,
    mean_temps: float,
    std_temps: float
) -> float:
    """
    Calcule le score en tenant compte de la vitesse.

    Seuil de similarité : ±1 écart-type autour de la moyenne

    Scénarios :
    - VRAI & Similaire (dans ±1σ)   → +1
    - VRAI & Plus rapide (>1σ)      → +3
    - VRAI & Plus lent (>1σ)        → +0.8
    - FAUX & Similaire (dans ±1σ)   → -1
    - FAUX & Plus rapide (>1σ)      → -2
    - FAUX & Plus lent (>1σ)        → -2
    """
    if std_temps == 0 or mean_temps == 0:
        return 1.0 if etat == "VRAI" else -1.0

    zone_min = mean_temps - std_temps
    zone_max = mean_temps + std_temps

    if etat == "VRAI":
        if temps_seconds < zone_min:
            score = 3.0    # Plus rapide → récompense
        elif temps_seconds > zone_max:
            score = 0.8    # Plus lent → légère pénalité
        else:
            score = 1.0    # Similaire → score de base
    else:  # FAUX
        if zone_min <= temps_seconds <= zone_max:
            score = -1.0   # Similaire → score de base
        else:
            score = -2.0   # Plus rapide ou plus lent → pénalité

    logger.info(f"[SCORING] Vitesse: etat={etat}, temps={temps_seconds:.2f}s, mean={mean_temps:.2f}s, std={std_temps:.2f}s, zone=[{zone_min:.2f}, {zone_max:.2f}], score={score}")
    return score


# ─────────────────────────────────────────────
# CALCUL MARGE D'ERREUR
# ─────────────────────────────────────────────
def calculate_marge_score(
    etat: str,
    marge_erreur: float,
    mean_marge: float,
    std_marge: float
) -> float:
    """
    Calcule le bonus/malus de précision.
    S'applique UNIQUEMENT sur les FAUX.

    Scénarios :
    - VRAI                                    → 0 (pas de bonus marge)
    - FAUX & Marge similaire (±1σ)            → -1
    - FAUX & Drastiquement plus précis (>1σ)  → 0
    - FAUX & Drastiquement moins précis (>1σ) → -2
    """
    if etat == "VRAI":
        return 0.0

    if std_marge == 0 or mean_marge == 0:
        return -1.0

    zone_min = mean_marge - std_marge
    zone_max = mean_marge + std_marge

    if marge_erreur < zone_min:
        score = 0.0    # Plus précis que d'habitude → récompense
    elif marge_erreur > zone_max:
        score = -2.0   # Moins précis → pénalité
    else:
        score = -1.0   # Similaire → score de base

    logger.info(f"[SCORING] Marge: etat={etat}, marge={marge_erreur:.2f}%, mean={mean_marge:.2f}%, std={std_marge:.2f}%, zone=[{zone_min:.2f}, {zone_max:.2f}], score={score}")
    return score


# ─────────────────────────────────────────────
# CALCUL SCORE FINAL
# ─────────────────────────────────────────────
def calculate_final_score(
    etat: str,
    temps_seconds: float,
    marge_erreur: float,
    historical_data: list
) -> dict:
    """
    Calcule le score final avec tous les facteurs.

    Retourne :
    {
        "Score": int,
        "bonus_vitesse": float,
        "bonus_marge": float,
        "score_global": int
    }
    """
    score_base = 1 if etat == "VRAI" else -1

    # Pas assez d'historique → score de base uniquement
    if len(historical_data) < 5:
        logger.info(f"[SCORING] Not enough historical data ({len(historical_data)} entries) → base score only")
        return {
            "Score": score_base,
            "bonus_vitesse": 0.0,
            "bonus_marge": 0.0,
            "score_global": score_base
        }

    # Calculer stats vitesse (sur toutes les observations)
    temps_list = [d["Temps_Seconds"] for d in historical_data if d.get("Temps_Seconds") is not None]
    mean_temps = np.mean(temps_list) if temps_list else temps_seconds
    std_temps = np.std(temps_list) if len(temps_list) > 1 else 0

    # Calculer stats marge (sur les FAUX uniquement)
    marge_list = [d["Marge_Erreur"] for d in historical_data
                  if d.get("Marge_Erreur") is not None and d.get("Etat") == "FAUX"]
    mean_marge = np.mean(marge_list) if marge_list else marge_erreur
    std_marge = np.std(marge_list) if len(marge_list) > 1 else 0

    # Calculer les scores
    score_vitesse = calculate_vitesse_score(etat, temps_seconds, mean_temps, std_temps)
    score_marge = calculate_marge_score(etat, marge_erreur, mean_marge, std_marge)

    # bonus = écart au score de base
    bonus_vitesse = round(score_vitesse - score_base, 2)
    bonus_marge = round(score_marge, 2) if etat == "FAUX" else 0.0

    # Score global arrondi à l'entier
    score_global = round(score_vitesse + score_marge)

    logger.info(f"[SCORING] Final: base={score_base}, bonus_vitesse={bonus_vitesse}, bonus_marge={bonus_marge}, global={score_global}")

    return {
        "Score": score_base,
        "bonus_vitesse": bonus_vitesse,
        "bonus_marge": bonus_marge,
        "score_global": score_global
    }


# ─────────────────────────────────────────────
# CALCUL MALUS RÉGULARITÉ
# ─────────────────────────────────────────────
def calculate_regularity_malus(last_training_date) -> dict:
    """
    Calcule le malus de régularité selon les jours d'inactivité.

    Barème :
    - Jours 1-7   : -5 pixels/jour
    - Jours 8-14  : -8 pixels/jour
    - Jours 15-21 : -12 pixels/jour
    - Jours 22+   : -100 pixels/jour
    """
    if last_training_date is None:
        return {"malus": 0, "jours_inactif": 0}

    if isinstance(last_training_date, str):
        from datetime import datetime
        last_training_date = datetime.strptime(last_training_date, "%Y-%m-%d").date()

    jours_inactif = (date.today() - last_training_date).days

    if jours_inactif <= 0:
        return {"malus": 0, "jours_inactif": 0}

    malus = 0
    for jour in range(1, jours_inactif + 1):
        if jour <= 7:
            malus += 5
        elif jour <= 14:
            malus += 8
        elif jour <= 21:
            malus += 12
        else:
            malus += 100

    logger.info(f"[SCORING] Regularity malus: {jours_inactif} days inactive → -{malus} pixels")
    return {"malus": malus, "jours_inactif": jours_inactif}
