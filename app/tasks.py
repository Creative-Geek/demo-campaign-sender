# app/tasks.py
"""Celery tasks for sending campaign emails with retries and idempotency."""

from datetime import datetime, timezone

from app.celery_app import celery
from app.database import SessionLocal
from app.email_service import send_email, EmailServiceError
from app.models import SendLog


@celery.task(
    name="send_single_email",
    bind=True, # enables access to self.request.retries
    autoretry_for=(EmailServiceError,), # automatically retry on network timeout
    max_retries=3, # give up after 3 attempts
    retry_backoff=True, # wait exponentially longer (1s, 2s, 4s...)
    retry_backoff_max=30, # cap backoff wait time to 30s
)
def send_single_email(self, campaign_id: int, recipient_email: str, subject: str, body: str):
    """Worker task: sends one email idempotently, skipping if already delivered."""
    db = SessionLocal() # open isolated session for worker
    try:
        idempotency_key = f"{campaign_id}-{recipient_email}" # unique compound identity

        existing = db.query(SendLog).filter_by(
            idempotency_key=idempotency_key,
            status="sent",
        ).first()
        if existing:
            return {"status": "skipped", "to": recipient_email, "reason": "already sent"} # safe no-op on duplicate

        send_email(to=recipient_email, subject=subject, body=body) # blocks worker, not user web request
        log = SendLog(
            campaign_id=campaign_id,
            recipient_email=recipient_email,
            status="sent",
            idempotency_key=idempotency_key,
            sent_at=datetime.now(timezone.utc),
        )
        db.add(log)
        db.commit() # save successful delivery
        return {"status": "sent", "to": recipient_email}
    except EmailServiceError as e:
        if getattr(self.request, "retries", 0) >= self.max_retries: # only record failure when retries run out
            log = SendLog(
                campaign_id=campaign_id,
                recipient_email=recipient_email,
                status="failed",
                error=str(e),
                idempotency_key=idempotency_key,
            )
            db.add(log)
            db.commit() # save failure after all retries fail
        raise e # re-raise so celery handles retry scheduling
    finally:
        db.close() # always release database connection
