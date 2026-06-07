from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.services.auto_email_sync_service import run_auto_email_sync_once
from app.services.reminder_service import run_due_reminder_calls

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _should_start_scheduler() -> bool:
    if not settings.auto_email_sync_enabled and not settings.reminder_calls_enabled:
        return False
    run_main = settings.scheduler_run_identifier.lower()
    if run_main in {"", "true", "1"}:
        return True
    return False


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return
    if not _should_start_scheduler():
        return

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        run_auto_email_sync_once,
        trigger=IntervalTrigger(minutes=settings.auto_email_sync_interval_minutes),
        id="auto-email-sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    if settings.reminder_calls_enabled:
        _scheduler.add_job(
            run_due_reminder_calls,
            trigger=IntervalTrigger(seconds=settings.reminder_check_interval_seconds),
            id="reminder-due-check",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    _scheduler.start()
    logger.warning(
        "Scheduler started auto_email_sync_enabled=%s reminder_calls_enabled=%s",
        settings.auto_email_sync_enabled,
        settings.reminder_calls_enabled,
    )
    if settings.reminder_calls_enabled:
        logger.warning("Reminder call scheduler started interval_seconds=%s enabled=%s", settings.reminder_check_interval_seconds, settings.reminder_calls_enabled)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    _scheduler = None
