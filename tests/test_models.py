# tests/test_models.py
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Campaign, Recipient, SendLog


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_create_campaign_with_recipients():
    session = _make_session()
    campaign = Campaign(name="Welcome Wave", subject="Hello!", body="Welcome to the team.")
    session.add(campaign)
    session.commit()

    r1 = Recipient(campaign_id=campaign.id, email="a@example.com")
    r2 = Recipient(campaign_id=campaign.id, email="b@example.com")
    session.add_all([r1, r2])
    session.commit()

    assert session.query(Recipient).filter_by(campaign_id=campaign.id).count() == 2


def test_send_log_idempotency_key_unique():
    session = _make_session()
    campaign = Campaign(name="Test", subject="S", body="B")
    session.add(campaign)
    session.commit()

    log1 = SendLog(
        campaign_id=campaign.id,
        recipient_email="a@example.com",
        status="sent",
        idempotency_key="campaign-1-a@example.com",
    )
    session.add(log1)
    session.commit()

    log2 = SendLog(
        campaign_id=campaign.id,
        recipient_email="a@example.com",
        status="sent",
        idempotency_key="campaign-1-a@example.com",  # duplicate key
    )
    session.add(log2)
    try:
        session.commit()
        assert False, "Should have raised IntegrityError"
    except Exception:
        session.rollback()


def test_campaign_default_status_is_draft():
    session = _make_session()
    campaign = Campaign(name="Test", subject="S", body="B")
    session.add(campaign)
    session.commit()
    assert campaign.status == "draft"
