# app/main.py
"""FastAPI app — Phase 0: Everything is synchronous and broken."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.email_service import send_email, EmailServiceError
from app.models import Campaign, Recipient, SendLog


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db() # create sqlite tables on boot
    yield


app = FastAPI(title="Campaign Sender (Broken Edition)", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def home():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(template_path, encoding="utf-8") as f:
        return f.read()


@app.get("/api/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).all()
    result = []
    for c in campaigns:
        count = db.query(Recipient).filter_by(campaign_id=c.id).count()
        result.append({
            "id": c.id,
            "name": c.name,
            "subject": c.subject,
            "status": c.status,
            "recipient_count": count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return result


@app.post("/api/campaigns/{campaign_id}/send")
def send_campaign_sync(campaign_id: int, db: Session = Depends(get_db)):
    """The broken endpoint: sends emails one-by-one inside the request."""
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    campaign.status = "sending"
    db.commit()

    recipients = db.query(Recipient).filter_by(campaign_id=campaign_id).all()

    sent = 0
    failed = 0

    for recipient in recipients: # loop through all recipients synchronously
        try:
            send_email( # blocks thread for 0.3s to 1.5s per recipient
                to=recipient.email,
                subject=campaign.subject,
                body=campaign.body,
            )
            log = SendLog(
                campaign_id=campaign_id,
                recipient_email=recipient.email,
                status="sent",
                idempotency_key=f"{campaign_id}-{recipient.email}",
                sent_at=datetime.now(timezone.utc),
            )
            db.add(log)
            db.commit() # commit each send individually
            sent += 1
        except EmailServiceError as e:
            log = SendLog(
                campaign_id=campaign_id,
                recipient_email=recipient.email,
                status="failed",
                error=str(e),
                idempotency_key=f"{campaign_id}-{recipient.email}",
            )
            db.add(log)
            db.commit() # log failure
            failed += 1

    campaign.status = "sent" if failed == 0 else "failed"
    db.commit()

    return {"total": len(recipients), "sent": sent, "failed": failed}


@app.get("/api/campaigns/{campaign_id}/status")
def campaign_status(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    total = db.query(Recipient).filter_by(campaign_id=campaign_id).count()
    sent = db.query(SendLog).filter_by(campaign_id=campaign_id, status="sent").count()
    failed = db.query(SendLog).filter_by(campaign_id=campaign_id, status="failed").count()

    return {
        "campaign_id": campaign_id,
        "status": campaign.status,
        "total": total,
        "sent": sent,
        "failed": failed,
        "pending": max(0, total - sent - failed), # clamp to 0 in case of orphan logs
    }
