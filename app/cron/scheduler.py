# app/cron/scheduler.py
"""
Système de planification des tâches récurrentes (cron jobs).
Utilise APScheduler pour gérer les notifications push automatiques.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import pytz

logger = logging.getLogger(__name__)

# Timezone Paris
PARIS_TZ = pytz.timezone('Europe/Paris')

# Scheduler global
scheduler: AsyncIOScheduler = None


def init_scheduler():
    """
    Initialise le scheduler APScheduler.
    À appeler au démarrage de l'application FastAPI.
    """
    global scheduler
    
    if scheduler is not None:
        logger.warning("[Scheduler] Déjà initialisé")
        return scheduler
    
    scheduler = AsyncIOScheduler(timezone=PARIS_TZ)
    
    logger.info("[Scheduler] Initialisation des tâches planifiées...")
    
    # Import des tâches
    from .ranking_checker import check_rankings

    # NOTE: Rappels quotidiens (daily_reminder) désactivés
    # NOTE: Notifications du matin (morning_quote) désactivées

    # 1) Vérification des classements - Toutes les 30 minutes
    scheduler.add_job(
        check_rankings,
        CronTrigger(minute='*/30', timezone=PARIS_TZ),
        id='ranking_checker',
        name='Vérification classements',
        replace_existing=True
    )
    logger.info("[Scheduler] ✓ Vérification classements programmée (toutes les 30 min)")
    
    # Démarrer le scheduler
    scheduler.start()
    logger.info("[Scheduler] 🚀 Scheduler démarré avec succès")
    
    return scheduler


def shutdown_scheduler():
    """
    Arrête proprement le scheduler.
    À appeler lors de l'arrêt de l'application.
    """
    global scheduler
    
    if scheduler is not None:
        scheduler.shutdown(wait=True)
        logger.info("[Scheduler] Arrêté proprement")
        scheduler = None


def get_scheduler():
    """
    Retourne le scheduler (pour inspection ou modification).
    """
    return scheduler