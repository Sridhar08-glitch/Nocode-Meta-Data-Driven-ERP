"""
Collections Celery beats (F2).

``run_late_fees`` charges the one-time late fee on installments past their grace window;
``run_reminders`` fires due/overdue reminders; ``run_dunning`` escalates overdue installments.
All iterate every workspace (ORM ``workspace_id`` filter is the isolation line).
"""
from __future__ import annotations

from celery import shared_task

from .services import CollectionsService


@shared_task(name="collections.run_late_fees")
def run_late_fees() -> dict:
    return {"charged": CollectionsService.run_late_fees()}


@shared_task(name="collections.run_reminders")
def run_reminders() -> dict:
    return {"reminders_sent": CollectionsService.run_reminders()}


@shared_task(name="collections.run_dunning")
def run_dunning() -> dict:
    return {"escalated": CollectionsService.run_dunning()}
