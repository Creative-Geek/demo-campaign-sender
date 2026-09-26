# app/tasks.py
"""Celery tasks for sending campaign emails asynchronously."""

from datetime import datetime, timezone

from app.celery_app import celery
from app.database import SessionLocal
from app.email_service import send_email, EmailServiceError
from app.models import SendLog


@celery.task(name="send_single_email")
def send_single_email(campaign_id: int, recipient_email: str, subject: str, body: str):
    """Worker task: sends one email in the background and logs the result."""
    db = SessionLocal() # open isolated session for this worker process
    try:
        send_email(to=recipient_email, subject=subject, body=body) # blocks worker, not user web request
        log = SendLog(
            campaign_id=campaign_id,
            recipient_email=recipient_email,
            status="sent",
            idempotency_key=f"{campaign_id}-{recipient_email}",
            sent_at=datetime.now(timezone.utc),
        )
        db.add(log)
        db.commit() # save successful delivery
        return {"status": "sent", "to": recipient_email}
    except EmailServiceError as e:
        log = SendLog(
            campaign_id=campaign_id,
            recipient_email=recipient_email,
            status="failed",
            error=str(e),
            idempotency_key=f"{campaign_id}-{recipient_email}",
        )
        db.add(log)
        db.commit() # save failure details
        return {"status": "failed", "to": recipient_email, "error": str(e)}
    finally:
        db.close() # always release database connection
