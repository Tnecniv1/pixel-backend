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
    from .daily_reminder import send_daily_reminders
    from .ranking_checker import check_rankings

    # 1) Rappels quotidiens - 20:00 heure de Paris
    scheduler.add_job(
        send_daily_reminders,
        CronTrigger(hour=20, minute=0, timezone=PARIS_TZ),
        id='daily_reminder',
        name='Rappels quotidiens',
        replace_existing=True
    )
    logger.info("[Scheduler] ✓ Rappels quotidiens programmés (20:00 Paris)")

    # NOTE: Notifications du matin (morning_quote) désactivées

    # 2) Vérification des classements - Toutes les 30 minutes
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