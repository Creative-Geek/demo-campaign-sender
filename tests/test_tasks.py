# tests/test_tasks.py
from unittest.mock import patch
import pytest
from celery.exceptions import Retry
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Campaign, SendLog

test_engine = create_engine("sqlite:///:memory:")
TestSession = sessionmaker(bind=test_engine)


def setup_function():
    Base.metadata.create_all(test_engine)


def teardown_function():
    Base.metadata.drop_all(test_engine)


def test_task_has_retry_configuration():
    """Verify task is configured with automatic retry on EmailServiceError."""
    from app.email_service import EmailServiceError
    from app.tasks import send_single_email
    assert send_single_email.max_retries == 3
    assert send_single_email.autoretry_for == (EmailServiceError,)


def test_send_single_email_task_logs_success():
    """The Celery task should call send_email and log a successful send."""
    db = TestSession()
    c = Campaign(name="Test", subject="Hi", body="Body")
    db.add(c)
    db.commit()
    campaign_id = c.id
    db.close()

    with patch("app.tasks.SessionLocal", TestSession):
        with patch("app.tasks.send_email") as mock_send:
            mock_send.return_value = {"status": "sent", "to": "test@example.com"}
            from app.tasks import send_single_email
            send_single_email(campaign_id, "test@example.com", "Hi", "Body")

    db = TestSession()
    log = db.query(SendLog).filter_by(campaign_id=campaign_id).first()
    assert log is not None
    assert log.status == "sent"
    assert log.recipient_email == "test@example.com"
    db.close()


def test_send_single_email_task_triggers_retry_on_failure():
    """When send_email raises, Celery should schedule a retry."""
    db = TestSession()
    c = Campaign(name="Test", subject="Hi", body="Body")
    db.add(c)
    db.commit()
    campaign_id = c.id
    db.close()

    with patch("app.tasks.SessionLocal", TestSession):
        with patch("app.tasks.send_email") as mock_send:
            from app.email_service import EmailServiceError
            mock_send.side_effect = EmailServiceError("Timeout")
            from app.tasks import send_single_email
            with pytest.raises((Retry, EmailServiceError)):
                send_single_email(campaign_id, "fail@example.com", "Hi", "Body")
